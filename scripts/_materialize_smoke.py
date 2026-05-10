"""Deterministic smoke for the Phase 1 materialize loop.

Builds a temporary sheet that mirrors the §23.3 customer-enrichment
scenario from the design overview, drives it through the SDK with a
``StubAIClient`` so no live API key is required, and asserts the
expected end-to-end behavior. Invoked by ``scripts/smoke-materialize.sh``
behind ``make verify``.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import textwrap
import unittest.mock as mock
from pathlib import Path

import folio
from folio._ai_kind import StubAIClient

CONTRACT = textwrap.dedent(
    """
    apiVersion: v3.0.0
    kind: DataContract
    id: smoke-customers
    name: smoke-customers
    version: 1.0.0
    description: Customer master smoke
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
            x-editable-by: ["agent:enrichment-bot", "human:*"]
    """
).strip()


DERIVATION = textwrap.dedent(
    """
    targets: [industry_tag]
    inputs: [company_name]
    kind: ai
    model: claude-sonnet-4-6
    prompt: |
      Single English word for the industry of {{ company_name }}.
    output: text
    materialization:
      trigger: on_demand
      respect_human_override: true
    """
).strip()


RECORDS = (
    '{"id":"cust_001","company_name":"Acme Manufacturing Inc","industry_tag":"Manufacturing"}\n'
    '{"id":"cust_002","company_name":"DataFlow Technologies","industry_tag":null}\n'
    '{"id":"cust_003","company_name":"Green Farm Co.","industry_tag":null}\n'
)


def _build_sheet(root: Path) -> Path:
    sheet = root / "customers"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(CONTRACT, encoding="utf-8")
    (sheet / "records.jsonl").write_text(RECORDS, encoding="utf-8")
    derivations = sheet / "derivations"
    derivations.mkdir()
    (derivations / "industry_tag.yaml").write_text(DERIVATION, encoding="utf-8")
    return sheet


def _expect(label: str, expected: object, actual: object) -> None:
    if expected != actual:
        raise AssertionError(
            f"smoke-materialize: {label} expected {expected!r}, got {actual!r}"
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="folio-mat-smoke-") as tmp:
        root = Path(tmp)
        cache_dir = root / "cache"

        # Redirect cache placement to a temp dir so the smoke is hermetic.
        with mock.patch(
            "folio._cache.default_cache_root",
            lambda sheet_id: cache_dir / sheet_id,
        ):
            sheet_path = _build_sheet(root)
            sheet = folio.open_sheet(sheet_path, actor="agent:enrichment-bot")

            # 1. validate
            contract = sheet.get_contract()
            _expect("contract id", "smoke-customers", contract.id)

            # 2. count records without industry
            null_rows = sheet.query(
                "SELECT COUNT(*) AS n FROM records WHERE industry_tag IS NULL"
            )
            _expect("null industry count", 2, null_rows[0]["n"])

            # 3. materialize via stub
            client = StubAIClient()
            client.prepare("DataFlow Technologies", "Software")
            client.prepare("Green Farm Co.", "Agriculture")
            client.prepare("Acme Manufacturing", "Manufacturing")  # already filled

            result = sheet.materialize(ai_client=client)
            if result["failures"]:
                raise AssertionError(
                    f"smoke-materialize: unexpected failures: {result['failures']}"
                )
            _expect("materialized count", 3, result["materialized"])

            # 4. distribution
            distribution = sheet.query(
                "SELECT industry_tag, COUNT(*) AS n FROM records GROUP BY 1 ORDER BY 1"
            )
            counts = {row["industry_tag"]: row["n"] for row in distribution}
            _expect("Manufacturing count", 1, counts.get("Manufacturing"))
            _expect("Software count", 1, counts.get("Software"))
            _expect("Agriculture count", 1, counts.get("Agriculture"))

            # 5. human override
            sheet.upsert_records(
                [{"id": "cust_003", "industry_tag": "AgTech"}],
                actor="human:yuta",
            )

            from folio._provenance import append_provenance

            append_provenance(
                sheet_path,
                {
                    "record_id": "cust_003",
                    "field": "industry_tag",
                    "source": "human_override",
                    "actor": "human:yuta",
                    "at": "2026-05-09T11:00:00Z",
                },
            )

            # 6. provenance history reflects both ai and human_override
            history = sheet.provenance("cust_003", "industry_tag", history=True)
            sources = [entry["source"] for entry in history]
            if sources != ["ai", "human_override"]:
                raise AssertionError(
                    f"smoke-materialize: provenance history expected ['ai', 'human_override'], got {sources}"
                )

            # 7. status counts
            status = sheet.materialization_status(targets=["industry_tag"])
            entry = status["industry_tag"]
            if entry["ai_count"] != 3:
                raise AssertionError(
                    f"smoke-materialize: ai_count expected 3, got {entry['ai_count']}"
                )
            if entry["human_override_count"] != 1:
                raise AssertionError(
                    f"smoke-materialize: human_override_count expected 1, got {entry['human_override_count']}"
                )

            # 8. force=True bypasses the override
            forced = sheet.materialize(ai_client=client, force=True)
            if forced["materialized"] < 1:
                raise AssertionError(
                    f"smoke-materialize: force materialize should recompute, got {forced}"
                )

    print("smoke-materialize: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
