"""Deterministic MCP smoke for FOLIO-H-017.

Builds a temp sheet, instantiates the FastMCP server with a
``StubAIClient`` so the smoke runs offline, and walks every tool through
FastMCP's in-process ``Client`` harness.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import textwrap
import unittest.mock as mock
from pathlib import Path
from typing import Any

from fastmcp import Client

from folio._ai_kind import StubAIClient
from folio_mcp import build_server


CONTRACT = textwrap.dedent(
    """
    apiVersion: v3.0.0
    kind: DataContract
    id: mcp-smoke
    name: mcp-smoke
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
            f"smoke-mcp: {label} expected {expected!r}, got {actual!r}"
        )


def _data(result: Any) -> Any:
    data = getattr(result, "data", None)
    if data is not None:
        return data
    content = getattr(result, "content", None) or []
    import json

    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            return json.loads(text)
    return result


async def _walk(server) -> None:
    async with Client(server) as client:
        contract = _data(await client.call_tool("get_contract", {"sheet_path": "customers"}))
        _expect("contract id", "mcp-smoke", contract["id"])

        rows = _data(
            await client.call_tool(
                "query",
                {
                    "sheet_path": "customers",
                    "sql": "SELECT COUNT(*) AS n FROM records WHERE industry_tag IS NULL",
                },
            )
        )
        _expect("null industry count", 2, rows[0]["n"])

        materialize_result = _data(
            await client.call_tool(
                "materialize",
                {"sheet_path": "customers"},
            )
        )
        if materialize_result["failures"]:
            raise AssertionError(
                f"smoke-mcp: unexpected failures: {materialize_result['failures']}"
            )
        _expect("materialized count", 2, materialize_result["materialized"])

        listing = _data(
            await client.call_tool(
                "list_records",
                {
                    "sheet_path": "customers",
                    "fields": ["id", "industry_tag"],
                    "limit": 10,
                    "format": "toon",
                },
            )
        )
        _expect("list format", "toon", listing["format"])
        if not isinstance(listing["records"], str) or not listing["records"].startswith(
            "[2]{id, industry_tag}:"
        ):
            raise AssertionError(
                f"smoke-mcp: toon header missing; got {listing['records']!r}"
            )

        single = _data(
            await client.call_tool(
                "get_record",
                {"sheet_path": "customers", "id": "cust_001"},
            )
        )
        _expect("get_record industry", "Manufacturing", single["industry_tag"])

        history = _data(
            await client.call_tool(
                "provenance",
                {
                    "sheet_path": "customers",
                    "record_id": "cust_001",
                    "field": "industry_tag",
                    "history": True,
                },
            )
        )
        if not isinstance(history, list) or history[0]["source"] != "ai":
            raise AssertionError(f"smoke-mcp: provenance history mismatch: {history!r}")

        delete_result = _data(
            await client.call_tool(
                "delete_records",
                {
                    "sheet_path": "customers",
                    "ids": ["cust_002"],
                    "actor": "human:smoke",
                },
            )
        )
        _expect("delete count", 1, delete_result["deleted"])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="folio-mcp-smoke-") as tmp:
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
            server = build_server(
                root=root,
                default_actor="agent:enrichment",
                ai_client=stub,
            )
            asyncio.run(_walk(server))

    print("smoke-mcp: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
