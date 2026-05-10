"""Tests for ``folio._import_kind`` (Phase 1 import-kind execution)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from folio._import_kind import (
    ImportSourceError,
    apply_import,
    load_import_source,
)
from folio.derivation import ImportDerivation

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "import-kind"


@pytest.fixture
def sheet_with_sources(tmp_path: Path) -> Path:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    refs = sheet / "refs"
    refs.mkdir()
    shutil.copy(FIXTURE_ROOT / "customers.csv", refs / "customers.csv")
    shutil.copy(FIXTURE_ROOT / "legacy.jsonl", refs / "legacy.jsonl")
    # JSON variant generated from the same data.
    (refs / "customers.json").write_text(
        '[{"id": "cust_001", "industry_tag": "Manufacturing"},'
        ' {"id": "cust_002", "industry_tag": "Software"}]',
        encoding="utf-8",
    )
    return sheet


# --- load_import_source ---------------------------------------------------


def test_load_csv_source(sheet_with_sources: Path) -> None:
    rows = load_import_source(sheet_with_sources, "refs/customers.csv")
    ids = [row["id"] for row in rows]
    assert ids == ["cust_001", "cust_002", "cust_003"]
    assert rows[0]["industry_tag"] == "Manufacturing"


def test_load_jsonl_source(sheet_with_sources: Path) -> None:
    rows = load_import_source(sheet_with_sources, "refs/legacy.jsonl")
    assert rows == [
        {"id": "cust_001", "legacy_customer_id": "L-100"},
        {"id": "cust_002", "legacy_customer_id": "L-200"},
    ]


def test_load_json_source(sheet_with_sources: Path) -> None:
    rows = load_import_source(sheet_with_sources, "refs/customers.json")
    assert len(rows) == 2
    assert rows[0]["industry_tag"] == "Manufacturing"


def test_missing_source_raises(sheet_with_sources: Path) -> None:
    with pytest.raises(ImportSourceError, match="not found"):
        load_import_source(sheet_with_sources, "refs/missing.csv")


def test_unsupported_extension_rejected(
    sheet_with_sources: Path, tmp_path: Path
) -> None:
    parquet = sheet_with_sources / "refs" / "x.parquet"
    parquet.write_bytes(b"\x00")
    with pytest.raises(ImportSourceError, match="unsupported import source"):
        load_import_source(sheet_with_sources, "refs/x.parquet")


def test_source_must_live_under_sheet(sheet_with_sources: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.csv"
    outside.write_text("id,x\n1,one\n", encoding="utf-8")
    with pytest.raises(ImportSourceError, match="under the sheet directory"):
        load_import_source(sheet_with_sources, "../outside.csv")


def test_invalid_jsonl_line_rejected(sheet_with_sources: Path) -> None:
    bad = sheet_with_sources / "refs" / "bad.jsonl"
    bad.write_text('{"ok": 1}\nnope\n', encoding="utf-8")
    with pytest.raises(ImportSourceError, match="invalid JSON"):
        load_import_source(sheet_with_sources, "refs/bad.jsonl")


def test_json_must_be_list_of_objects(sheet_with_sources: Path) -> None:
    bad = sheet_with_sources / "refs" / "bad.json"
    bad.write_text('{"id": "x"}', encoding="utf-8")
    with pytest.raises(ImportSourceError, match="list of objects"):
        load_import_source(sheet_with_sources, "refs/bad.json")


# --- apply_import ---------------------------------------------------------


def _import_derivation(**overrides: object) -> ImportDerivation:
    payload: dict[str, object] = {
        "targets": ["industry_tag"],
        "kind": "import",
        "source": "refs/customers.csv",
        "key_field": "id",
        "value_field": "industry_tag",
    }
    payload.update(overrides)
    return ImportDerivation.model_validate(payload)


def test_apply_import_single_value_match(sheet_with_sources: Path) -> None:
    rows = load_import_source(sheet_with_sources, "refs/customers.csv")
    derivation = _import_derivation()
    assert apply_import(derivation, rows, "cust_002") == {
        "industry_tag": "Software",
    }


def test_apply_import_no_match_returns_empty(sheet_with_sources: Path) -> None:
    rows = load_import_source(sheet_with_sources, "refs/customers.csv")
    derivation = _import_derivation()
    assert apply_import(derivation, rows, "cust_999") == {}


def test_apply_import_multi_value_mapping(sheet_with_sources: Path) -> None:
    rows = load_import_source(sheet_with_sources, "refs/customers.csv")
    derivation = ImportDerivation.model_validate(
        {
            "targets": ["industry_tag", "hq_country"],
            "kind": "import",
            "source": "refs/customers.csv",
            "key_field": "id",
            "value_fields": {
                "industry_tag": "industry_tag",
                "hq_country": "headquarters_country",
            },
        }
    )

    result = apply_import(derivation, rows, "cust_001")

    assert result == {
        "industry_tag": "Manufacturing",
        "hq_country": "Japan",
    }


def test_apply_import_rejects_ambiguous_match() -> None:
    rows = [{"id": "a", "v": 1}, {"id": "a", "v": 2}]
    derivation = ImportDerivation.model_validate(
        {
            "targets": ["v"],
            "kind": "import",
            "source": "x.csv",
            "key_field": "id",
            "value_field": "v",
        }
    )
    with pytest.raises(ImportSourceError, match="rows where id="):
        apply_import(derivation, rows, "a")
