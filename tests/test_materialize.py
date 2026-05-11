"""Integration tests for ``Sheet.materialize`` (Phase 1 wiring)."""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest

from folio import open_sheet
from folio._ai_kind import StubAIClient
from folio._cache import default_cache_root
from folio._provenance import append_provenance


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "import-kind"


@pytest.fixture
def sheet_with_ai_derivation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            """
            apiVersion: v3.0.0
            kind: DataContract
            id: ai-test-{uid}
            name: ai-test
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

    # Redirect default cache root to a temp folder so each test starts cold.
    cache_dir = tmp_path / "cache-root"
    monkeypatch.setattr(
        "folio._cache.default_cache_root",
        lambda sheet_id: cache_dir / sheet_id,
    )
    return sheet


@pytest.fixture
def sheet_with_import_derivation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            """
            apiVersion: v3.0.0
            kind: DataContract
            id: import-test-{uid}
            name: import-test
            version: 1.0.0
            schema:
              - name: items
                physicalType: jsonl
                properties:
                  - name: id
                    logicalType: string
                    primaryKey: true
                    required: true
                  - name: industry_tag
                    logicalType: string
                    x-derived: true
            """
        )
        .strip()
        .replace("{uid}", tmp_path.name),
        encoding="utf-8",
    )
    (sheet / "records.jsonl").write_text(
        '{"id": "cust_001"}\n{"id": "cust_002"}\n',
        encoding="utf-8",
    )

    refs = sheet / "refs"
    refs.mkdir()
    shutil.copy(FIXTURE_ROOT / "customers.csv", refs / "customers.csv")

    derivations = sheet / "derivations"
    derivations.mkdir()
    (derivations / "industry_tag.yaml").write_text(
        textwrap.dedent(
            """
            targets: [industry_tag]
            inputs: []
            kind: import
            source: refs/customers.csv
            key_field: id
            value_field: industry_tag
            """
        ).strip(),
        encoding="utf-8",
    )

    cache_dir = tmp_path / "cache-root"
    monkeypatch.setattr(
        "folio._cache.default_cache_root",
        lambda sheet_id: cache_dir / sheet_id,
    )
    return sheet


# --- ai materialize -------------------------------------------------------


def test_materialize_ai_writes_records_and_provenance(
    sheet_with_ai_derivation: Path,
) -> None:
    sheet = open_sheet(sheet_with_ai_derivation, actor="agent:test")
    client = StubAIClient()
    client.prepare("Industry of Acme", "Manufacturing")
    client.prepare("Industry of DataFlow", "Software")

    result = sheet.materialize(ai_client=client)

    assert result["materialized"] == 2
    assert result["skipped"] == 0
    assert result["failures"] == []

    rows = sheet.query("SELECT id, industry_tag FROM records ORDER BY id")
    assert rows == [
        {"id": "cust_001", "industry_tag": "Manufacturing"},
        {"id": "cust_002", "industry_tag": "Software"},
    ]

    latest = sheet.provenance("cust_001", "industry_tag")
    assert latest is not None
    assert latest["source"] == "ai"
    assert latest["actor"] == "agent:test"
    assert latest["model"] == "claude-sonnet-4-6"


def test_materialize_ai_is_idempotent_via_cache_and_stale_check(
    sheet_with_ai_derivation: Path,
) -> None:
    sheet = open_sheet(sheet_with_ai_derivation, actor="agent:test")
    client = StubAIClient()
    client.prepare("Industry of Acme", "Manufacturing")
    client.prepare("Industry of DataFlow", "Software")

    first = sheet.materialize(ai_client=client)
    assert first["materialized"] == 2
    first_call_count = len(client.calls)

    second = sheet.materialize(ai_client=client)
    assert second["materialized"] == 0
    assert second["skipped"] == 2
    # Stale check short-circuits before the cache hit, so no new API call.
    assert len(client.calls) == first_call_count


def test_materialize_ai_force_recomputes_even_with_human_override(
    sheet_with_ai_derivation: Path,
) -> None:
    sheet = open_sheet(sheet_with_ai_derivation, actor="agent:test")
    client = StubAIClient()
    client.prepare("Industry of Acme", "Manufacturing")
    client.prepare("Industry of DataFlow", "Software")

    sheet.materialize(ai_client=client)

    # Mark cust_001 as a human override.
    append_provenance(
        sheet_with_ai_derivation,
        {
            "record_id": "cust_001",
            "field": "industry_tag",
            "source": "human_override",
            "actor": "human:alice",
            "at": "2099-01-01T00:00:00Z",
        },
    )

    # Without force, the override is honored.
    untouched = sheet.materialize(ai_client=client)
    assert untouched["skipped"] >= 1

    # With force, the override is bypassed.
    forced = sheet.materialize(ai_client=client, force=True)
    assert forced["materialized"] >= 1


def test_materialize_ai_failure_does_not_raise(
    sheet_with_ai_derivation: Path,
) -> None:
    sheet = open_sheet(sheet_with_ai_derivation, actor="agent:test")
    client = StubAIClient()
    # No canned response → AIKindError
    result = sheet.materialize(ai_client=client)
    assert result["materialized"] == 0
    assert len(result["failures"]) == 2
    error_types = {entry["error_type"] for entry in result["failures"]}
    assert error_types == {"AIKindError"}


def test_materialize_unknown_target_rejected(
    sheet_with_ai_derivation: Path,
) -> None:
    from folio.exceptions import OperationError

    sheet = open_sheet(sheet_with_ai_derivation, actor="agent:test")
    client = StubAIClient()
    with pytest.raises(OperationError, match="unknown derivation target"):
        sheet.materialize(targets=["does_not_exist"], ai_client=client)


# --- import materialize ---------------------------------------------------


def test_materialize_import_from_csv(sheet_with_import_derivation: Path) -> None:
    sheet = open_sheet(sheet_with_import_derivation, actor="agent:import")

    result = sheet.materialize(ai_client=StubAIClient())
    assert result["materialized"] == 2

    rows = sheet.query("SELECT id, industry_tag FROM records ORDER BY id")
    assert rows == [
        {"id": "cust_001", "industry_tag": "Manufacturing"},
        {"id": "cust_002", "industry_tag": "Software"},
    ]

    latest = sheet.provenance("cust_002", "industry_tag")
    assert latest is not None
    assert latest["source"] == "import"


# --- status + provenance --------------------------------------------------


def test_materialization_status_counts_sources(
    sheet_with_ai_derivation: Path,
) -> None:
    sheet = open_sheet(sheet_with_ai_derivation, actor="agent:test")
    client = StubAIClient()
    client.prepare("Industry of Acme", "Manufacturing")
    client.prepare("Industry of DataFlow", "Software")
    sheet.materialize(ai_client=client)

    append_provenance(
        sheet_with_ai_derivation,
        {
            "record_id": "cust_001",
            "field": "industry_tag",
            "source": "human_override",
            "actor": "human:alice",
            "at": "2099-01-01T00:00:00Z",
        },
    )

    status = sheet.materialization_status()
    assert "industry_tag" in status
    entry = status["industry_tag"]
    assert entry["total_records"] == 2
    assert entry["ai_count"] == 2
    assert entry["human_override_count"] == 1
    assert entry["with_provenance"] == 2


def test_provenance_history_returns_all_entries(
    sheet_with_ai_derivation: Path,
) -> None:
    sheet = open_sheet(sheet_with_ai_derivation, actor="agent:test")
    client = StubAIClient()
    client.prepare("Industry of Acme", "Manufacturing")
    client.prepare("Industry of DataFlow", "Software")
    sheet.materialize(ai_client=client)

    append_provenance(
        sheet_with_ai_derivation,
        {
            "record_id": "cust_001",
            "field": "industry_tag",
            "source": "human_override",
            "actor": "human:alice",
            "at": "2099-01-01T00:00:00Z",
        },
    )

    history = sheet.provenance("cust_001", "industry_tag", history=True)
    assert len(history) == 2
    assert history[0]["source"] == "ai"
    assert history[1]["source"] == "human_override"
