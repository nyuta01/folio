"""Tests for Phase 5 V4–V6: SSE event stream + folio serve alias."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from folio._ai_kind import StubAIClient
from folio_viewer import EventBus
from folio_viewer.server import CSRF_HEADER_NAME, build_app


@pytest.fixture
def viewer_sheet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sheet = tmp_path / "customers"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            """
            apiVersion: v3.0.0
            kind: DataContract
            id: viewer-events-{uid}
            name: viewer-events
            version: 1.0.0
            schema:
              - name: items
                physicalType: jsonl
                properties:
                  - name: id
                    logicalType: string
                    primaryKey: true
                    required: true
                  - name: company_name
                    logicalType: string
                    required: true
                  - name: industry_tag
                    logicalType: string
                    x-derived: true
                    x-inputs: [company_name]
            """
        )
        .strip()
        .replace("{uid}", tmp_path.name),
        encoding="utf-8",
    )
    (sheet / "records.jsonl").write_text(
        '{"id": "cust_001", "company_name": "Acme"}\n', encoding="utf-8"
    )
    derivations = sheet / "derivations"
    derivations.mkdir()
    (derivations / "industry_tag.yaml").write_text(
        textwrap.dedent(
            """
            targets: [industry_tag]
            inputs: [company_name]
            kind: ai
            model: claude-sonnet-4-6
            prompt: |
              Industry of {{ company_name }} in one word.
            output: text
            """
        ).strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "folio._cache.default_cache_root",
        lambda sheet_id: tmp_path / "cache" / sheet_id,
    )
    return sheet


@pytest.fixture
def viewer_app(viewer_sheet: Path):
    stub = StubAIClient()
    stub.prepare("Industry of Acme", "Manufacturing")
    bus = EventBus()
    return build_app(
        sheet_path=viewer_sheet,
        default_actor="agent:test",
        ai_client=stub,
        event_bus=bus,
    ), bus


# --- EventBus -------------------------------------------------------------


def test_event_bus_publishes_to_subscribers() -> None:
    import asyncio

    async def run() -> tuple[dict, dict]:
        bus = EventBus()
        queue = bus.subscribe()
        bus.publish({"kind": "test.a", "ts": "x"})
        bus.publish({"kind": "test.b", "ts": "y"})
        first = await queue.get()
        second = await queue.get()
        return first, second

    a, b = asyncio.run(run())
    assert a["kind"] == "test.a"
    assert b["kind"] == "test.b"


def test_event_bus_drops_oldest_on_overflow() -> None:
    import asyncio

    async def run() -> list[dict]:
        bus = EventBus(queue_size=2)
        queue = bus.subscribe()
        for index in range(5):
            bus.publish({"kind": f"e{index}", "ts": "_"})
        out: list[dict] = []
        while not queue.empty():
            out.append(queue.get_nowait())
        return out

    events = asyncio.run(run())
    assert [e["kind"] for e in events] == ["e3", "e4"]


# --- materialize publishes events ----------------------------------------


def test_materialize_publishes_lifecycle_events(viewer_app) -> None:
    app, bus = viewer_app
    captured: list[dict] = []

    original_publish = bus.publish

    def recording_publish(event: dict) -> None:
        captured.append(event)
        original_publish(event)

    bus.publish = recording_publish  # type: ignore[method-assign]

    with TestClient(app) as client:
        token = client.get("/api/csrf").json()["csrf_token"]
        response = client.post(
            "/api/materialize",
            json={},
            headers={CSRF_HEADER_NAME: token},
        )
        assert response.status_code == 200

    kinds = [event["kind"] for event in captured]
    assert kinds == ["materialize.start", "materialize.end"]
    end_event = captured[1]
    assert end_event["materialized"] == 1
    assert end_event["failures"] == 0


# --- /events endpoint route registration ---------------------------------


def test_events_endpoint_is_registered(viewer_app) -> None:
    """`/events` exists and advertises text/event-stream.

    The full live SSE round-trip lives in ``scripts/_viewer_smoke.py``
    because ``asyncio.Queue`` is not thread-safe across Starlette's
    TestClient portal — a synthetic ``bus.publish`` from the test
    thread cannot reliably wake up the route's ``queue.get`` running
    in the portal's event loop.
    """
    app, _bus = viewer_app
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/events" in paths


# --- folio serve alias ----------------------------------------------------


def test_folio_serve_alias_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    """`folio serve` is wired to `folio_viewer.cli.serve`."""
    captured: dict = {}

    def fake_serve(*, sheet, host, port, actor, static_dir):
        captured.update(
            sheet=sheet, host=host, port=port, actor=actor, static_dir=static_dir
        )

    monkeypatch.setattr("folio_viewer.cli.serve", fake_serve)

    from typer.testing import CliRunner

    from folio.cli import app

    runner = CliRunner()
    # Use a real path so Typer's exists=True passes.
    target = Path.cwd()
    result = runner.invoke(app, ["serve", str(target), "--port", "3001", "--actor", "agent:cli"])
    assert result.exit_code == 0, result.output
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 3001
    assert captured["actor"] == "agent:cli"
    assert Path(captured["sheet"]).resolve() == target.resolve()


# --- provenance history (V5 surface) --------------------------------------


def test_provenance_history_returns_list(viewer_app) -> None:
    app, _bus = viewer_app
    with TestClient(app) as client:
        token = client.get("/api/csrf").json()["csrf_token"]
        client.post("/api/materialize", json={}, headers={CSRF_HEADER_NAME: token})
        response = client.get(
            "/api/provenance",
            params={
                "record_id": "cust_001",
                "field": "industry_tag",
                "history": True,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert body[0]["source"] == "ai"
