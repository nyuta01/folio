"""Tests for ``folio_mcp.server`` (Phase 3 MCP server, in-process)."""

from __future__ import annotations

import asyncio
import json
import shutil
import textwrap
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client

from folio._ai_kind import StubAIClient
from folio_mcp import build_server


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "import-kind"


@pytest.fixture
def mcp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a root directory with one sheet for MCP tests."""
    root = tmp_path / "mcp-root"
    root.mkdir()

    sheet = root / "customers"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            """
            apiVersion: v3.0.0
            kind: DataContract
            id: mcp-customers-{uid}
            name: mcp-customers
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
        '{"id": "cust_001", "company_name": "Acme"}\n'
        '{"id": "cust_002", "company_name": "DataFlow"}\n',
        encoding="utf-8",
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

    # Hermetic cache placement.
    monkeypatch.setattr(
        "folio._cache.default_cache_root",
        lambda sheet_id: tmp_path / "cache" / sheet_id,
    )
    return root


def _stub_with_canned() -> StubAIClient:
    client = StubAIClient()
    client.prepare("Industry of Acme", "Manufacturing")
    client.prepare("Industry of DataFlow", "Software")
    return client


async def _call(server, name: str, args: dict[str, Any]) -> Any:
    async with Client(server) as client:
        result = await client.call_tool(name, args)
    return _unwrap(result)


def _unwrap(result: Any) -> Any:
    """Pull the structured value out of a FastMCP ``CallToolResult``.

    ``.data`` is populated when the tool's return type is statically
    serializable. Tools that return ``Any`` fall back to text content
    blocks, which we parse as JSON.
    """
    data = getattr(result, "data", None)
    if data is not None:
        return data
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            return json.loads(text)
    return result


def _run(coro):
    return asyncio.run(coro)


# --- read tools ----------------------------------------------------------


def test_get_contract_returns_dump(mcp_root: Path) -> None:
    server = build_server(root=mcp_root)
    contract = _run(_call(server, "get_contract", {"sheet_path": "customers"}))
    assert contract["kind"] == "DataContract"
    assert contract["apiVersion"] == "v3.0.0"
    assert contract["schema"][0]["name"] == "items"


def test_query_returns_rows(mcp_root: Path) -> None:
    server = build_server(root=mcp_root)
    rows = _run(
        _call(
            server,
            "query",
            {
                "sheet_path": "customers",
                "sql": "SELECT id FROM records ORDER BY id",
            },
        )
    )
    assert rows == [{"id": "cust_001"}, {"id": "cust_002"}]


def test_list_records_default_json(mcp_root: Path) -> None:
    server = build_server(root=mcp_root)
    payload = _run(
        _call(
            server,
            "list_records",
            {"sheet_path": "customers", "fields": ["id"], "limit": 10},
        )
    )
    assert payload["format"] == "json"
    assert {row["id"] for row in payload["records"]} == {"cust_001", "cust_002"}


def test_list_records_toon(mcp_root: Path) -> None:
    server = build_server(root=mcp_root)
    payload = _run(
        _call(
            server,
            "list_records",
            {
                "sheet_path": "customers",
                "fields": ["id"],
                "limit": 10,
                "format": "toon",
            },
        )
    )
    assert payload["format"] == "toon"
    assert isinstance(payload["records"], str)
    assert payload["records"].startswith("[2]{id}:")


def test_get_record_returns_match(mcp_root: Path) -> None:
    server = build_server(root=mcp_root)
    row = _run(
        _call(
            server,
            "get_record",
            {"sheet_path": "customers", "id": "cust_002"},
        )
    )
    assert row["company_name"] == "DataFlow"


# --- write tools ---------------------------------------------------------


def test_upsert_and_delete_round_trip(mcp_root: Path) -> None:
    server = build_server(root=mcp_root, default_actor="agent:test")

    upsert_result = _run(
        _call(
            server,
            "upsert_records",
            {
                "sheet_path": "customers",
                "records": [{"id": "cust_003", "company_name": "Green Farm"}],
            },
        )
    )
    assert upsert_result["inserted"] == 1
    assert upsert_result["total"] == 3

    delete_result = _run(
        _call(
            server,
            "delete_records",
            {"sheet_path": "customers", "ids": ["cust_003"]},
        )
    )
    assert delete_result["deleted"] == 1


# --- materialize ---------------------------------------------------------


def test_materialize_uses_injected_stub_ai_client(mcp_root: Path) -> None:
    stub = _stub_with_canned()
    server = build_server(
        root=mcp_root,
        default_actor="agent:enrichment",
        ai_client=stub,
    )
    result = _run(
        _call(
            server,
            "materialize",
            {"sheet_path": "customers"},
        )
    )
    assert result["materialized"] == 2
    assert result["failures"] == []


def test_materialization_status_after_materialize(mcp_root: Path) -> None:
    stub = _stub_with_canned()
    server = build_server(
        root=mcp_root,
        default_actor="agent:enrichment",
        ai_client=stub,
    )
    _run(_call(server, "materialize", {"sheet_path": "customers"}))
    status = _run(
        _call(
            server,
            "materialization_status",
            {"sheet_path": "customers"},
        )
    )
    assert "industry_tag" in status
    assert status["industry_tag"]["ai_count"] == 2


def test_provenance_history(mcp_root: Path) -> None:
    stub = _stub_with_canned()
    server = build_server(
        root=mcp_root,
        default_actor="agent:enrichment",
        ai_client=stub,
    )
    _run(_call(server, "materialize", {"sheet_path": "customers"}))
    history = _run(
        _call(
            server,
            "provenance",
            {
                "sheet_path": "customers",
                "record_id": "cust_001",
                "field": "industry_tag",
                "history": True,
            },
        )
    )
    assert isinstance(history, list)
    assert history[0]["source"] == "ai"


# --- safety guards -------------------------------------------------------


def test_path_traversal_rejected(mcp_root: Path) -> None:
    server = build_server(root=mcp_root)
    with pytest.raises(Exception):
        _run(
            _call(
                server,
                "get_contract",
                {"sheet_path": "../escape"},
            )
        )


def test_missing_root_raises_at_build_time(tmp_path: Path) -> None:
    from folio.exceptions import SheetError

    with pytest.raises(SheetError, match="MCP root must be a directory"):
        build_server(root=tmp_path / "nope")
