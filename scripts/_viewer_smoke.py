"""Deterministic Viewer smoke for FOLIO-H-024.

Boots the FastAPI app under ``uvicorn`` on a random port, walks the
V0–V3 REST surface (contract, list, upsert with CSRF, query,
materialize, provenance), then tears the server down.

Runs offline: a ``StubAIClient`` provides canned responses so the
materialize round-trip never reaches the network.
"""

from __future__ import annotations

import contextlib
import json
import socket
import sys
import tempfile
import textwrap
import threading
import time
import unittest.mock as mock
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import uvicorn

from folio._ai_kind import StubAIClient
from folio_viewer.server import build_app


CONTRACT = textwrap.dedent(
    """
    apiVersion: v3.0.0
    kind: DataContract
    id: viewer-smoke
    name: viewer-smoke
    version: 1.0.0
    schema:
      - name: customers
        physicalType: jsonl
        properties:
          - name: id
            logicalType: string
            primaryKey: true
            required: true
          - name: company_name
            logicalType: string
            required: true
            x-editable-by: ["agent:smoke"]
          - name: industry_tag
            logicalType: string
            x-derived: true
            x-inputs: [company_name]
    """
).strip()


DERIVATION = textwrap.dedent(
    """
    targets: [industry_tag]
    inputs: [company_name]
    kind: ai
    model: claude-sonnet-4-6
    prompt: |
      Industry of {{ company_name }} in one word.
    output: text
    """
).strip()


RECORDS = (
    '{"id": "cust_001", "company_name": "Acme Manufacturing"}\n'
    '{"id": "cust_002", "company_name": "DataFlow"}\n'
)


def _expect(label: str, expected: Any, actual: Any) -> None:
    if expected != actual:
        raise AssertionError(
            f"smoke-viewer: {label} expected {expected!r}, got {actual!r}"
        )


def _free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_ready(base_url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/csrf", timeout=0.5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"smoke-viewer: server did not start: {last_error!r}")


def _request(
    base_url: str,
    method: str,
    path: str,
    *,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], Any]:
    data = None
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(f"{base_url}{path}", data=data, method=method)
    for key, value in request_headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=5.0) as response:
            payload = response.read()
            decoded = json.loads(payload) if payload else None
            return response.status, dict(response.headers.items()), decoded
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        decoded_err = json.loads(body_text) if body_text else None
        return exc.code, dict(exc.headers.items()) if exc.headers else {}, decoded_err


def _consume_events(base_url: str, cookie: str, expected_kinds: set[str]) -> set[str]:
    """Open ``/events`` and read until every kind in ``expected_kinds`` arrives.

    Times out after 10 s so a stuck pipeline fails the smoke loudly.
    """
    deadline = time.time() + 10.0
    seen: set[str] = set()
    req = urllib.request.Request(f"{base_url}/events")
    req.add_header("Cookie", cookie)
    req.add_header("Accept", "text/event-stream")
    with urllib.request.urlopen(req, timeout=10.0) as response:
        if response.status != 200:
            raise AssertionError(f"smoke-viewer: /events status {response.status}")
        while time.time() < deadline and not expected_kinds.issubset(seen):
            line = response.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip("\n")
            if text.startswith("data:"):
                payload = json.loads(text[len("data:"):].strip())
                seen.add(payload["kind"])
    return seen


def _walk(base_url: str) -> None:
    status, headers, csrf_body = _request(base_url, "GET", "/api/csrf")
    _expect("csrf status", 200, status)
    token = csrf_body["csrf_token"]
    cookie_header = headers.get("set-cookie") or headers.get("Set-Cookie") or ""
    if "folio_csrf" not in cookie_header:
        raise AssertionError(f"smoke-viewer: csrf cookie missing: {cookie_header!r}")
    cookie = cookie_header.split(";")[0]

    auth = {"Cookie": cookie, "X-CSRF-Token": token}

    status, _, contract = _request(base_url, "GET", "/api/contract", headers={"Cookie": cookie})
    _expect("contract status", 200, status)
    _expect("contract id", "viewer-smoke", contract["id"])

    status, _, listing = _request(
        base_url, "GET", "/api/records?fields=id,company_name", headers={"Cookie": cookie}
    )
    _expect("list status", 200, status)
    _expect("list count", 2, len(listing["records"]))

    # Open /events first so the SSE consumer is registered before
    # materialize publishes its lifecycle frames.
    sse_result: dict[str, set[str]] = {}

    def _sse_worker() -> None:
        sse_result["seen"] = _consume_events(
            base_url,
            cookie,
            expected_kinds={"materialize.start", "materialize.end"},
        )

    sse_thread = threading.Thread(target=_sse_worker, daemon=True)
    sse_thread.start()
    # Give the SSE subscriber a moment to register before publishing.
    time.sleep(0.2)

    status, _, materialize_result = _request(
        base_url,
        "POST",
        "/api/materialize",
        body={"actor": "agent:smoke"},
        headers=auth,
    )
    _expect("materialize status", 200, status)
    _expect("materialized count", 2, materialize_result["materialized"])
    if materialize_result["failures"]:
        raise AssertionError(
            f"smoke-viewer: unexpected failures: {materialize_result['failures']}"
        )

    sse_thread.join(timeout=12.0)
    seen = sse_result.get("seen", set())
    if not {"materialize.start", "materialize.end"}.issubset(seen):
        raise AssertionError(
            f"smoke-viewer: SSE missing lifecycle events; saw {sorted(seen)!r}"
        )

    status, _, prov = _request(
        base_url,
        "GET",
        "/api/provenance?record_id=cust_001&field=industry_tag",
        headers={"Cookie": cookie},
    )
    _expect("provenance status", 200, status)
    _expect("provenance source", "ai", prov["source"])

    status, _, query_body = _request(
        base_url,
        "POST",
        "/api/query",
        body={"sql": "SELECT COUNT(*) AS n FROM records WHERE industry_tag IS NOT NULL"},
        headers={"Cookie": cookie},
    )
    _expect("query status", 200, status)
    _expect("query count", 2, query_body["rows"][0]["n"])

    status, _, _ = _request(
        base_url,
        "POST",
        "/api/records",
        body={"records": [{"id": "cust_003", "company_name": "Green Farm"}], "actor": "agent:smoke"},
        headers=auth,
    )
    _expect("upsert status", 200, status)

    # CSRF rejection without the header.
    status, _, _ = _request(
        base_url,
        "DELETE",
        "/api/records?ids=cust_003",
        headers={"Cookie": cookie},
    )
    _expect("delete-without-csrf status", 403, status)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="folio-viewer-smoke-") as tmp:
        root = Path(tmp)
        cache_dir = root / "cache"

        sheet = root / "customers"
        sheet.mkdir()
        (sheet / "contract.yaml").write_text(CONTRACT, encoding="utf-8")
        (sheet / "records.jsonl").write_text(RECORDS, encoding="utf-8")
        derivations = sheet / "derivations"
        derivations.mkdir()
        (derivations / "industry_tag.yaml").write_text(DERIVATION, encoding="utf-8")

        stub = StubAIClient()
        stub.prepare("Acme Manufacturing", "Manufacturing")
        stub.prepare("DataFlow", "Software")

        with mock.patch(
            "folio._cache.default_cache_root",
            lambda sheet_id: cache_dir / sheet_id,
        ):
            app = build_app(
                sheet_path=sheet,
                default_actor="agent:smoke",
                ai_client=stub,
            )

            port = _free_port()
            config = uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
                lifespan="on",
            )
            server = uvicorn.Server(config)
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()

            try:
                base_url = f"http://127.0.0.1:{port}"
                _wait_until_ready(base_url)
                _walk(base_url)
            finally:
                server.should_exit = True
                thread.join(timeout=5.0)

    print("smoke-viewer: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
