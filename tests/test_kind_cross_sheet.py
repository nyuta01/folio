"""Tests for the Phase 4 ``cross_sheet`` extension kind."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from folio import open_sheet
from folio.derivation import DerivationError, load_derivation
from folio.kinds import (
    CrossSheetDerivation,
    execute_cross_sheet,
    foreign_records_hash,
    resolve_foreign_sheet,
)


CHILD_CONTRACT = textwrap.dedent(
    """
    apiVersion: v3.0.0
    kind: DataContract
    id: child
    name: child
    version: 1.0.0
    schema:
      - name: items
        physicalType: jsonl
        properties:
          - name: id
            logicalType: string
            primaryKey: true
            required: true
          - name: industry
            logicalType: string
            x-derived: true
    """
).strip()


PARENT_CONTRACT = textwrap.dedent(
    """
    apiVersion: v3.0.0
    kind: DataContract
    id: parent
    name: parent
    version: 1.0.0
    schema:
      - name: items
        physicalType: jsonl
        properties:
          - name: id
            logicalType: string
            primaryKey: true
            required: true
          - name: industry
            logicalType: string
    """
).strip()


def _build_pair(tmp_path: Path) -> tuple[Path, Path]:
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "contract.yaml").write_text(PARENT_CONTRACT, encoding="utf-8")
    (parent / "records.jsonl").write_text(
        '{"id": "p1", "industry": "Manufacturing"}\n'
        '{"id": "p2", "industry": "Software"}\n',
        encoding="utf-8",
    )

    child = tmp_path / "child"
    child.mkdir()
    (child / "contract.yaml").write_text(CHILD_CONTRACT, encoding="utf-8")
    (child / "records.jsonl").write_text(
        '{"id": "p1"}\n{"id": "p2"}\n{"id": "p3"}\n',
        encoding="utf-8",
    )
    derivations = child / "derivations"
    derivations.mkdir()
    (derivations / "industry.yaml").write_text(
        textwrap.dedent(
            """
            targets: [industry]
            inputs: []
            kind: cross_sheet
            source_sheet: ../parent
            key_field: id
            value_field: industry
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return parent, child


# --- Pydantic shape -------------------------------------------------------


def _write_yaml(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return path


def test_minimal_cross_sheet_loads(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "industry.yaml",
        """
        targets: [industry]
        inputs: []
        kind: cross_sheet
        source_sheet: ../parent
        key_field: id
        value_field: industry
        """,
    )
    derivation = load_derivation(path)
    assert isinstance(derivation, CrossSheetDerivation)
    assert derivation.value_field == "industry"


def test_cross_sheet_value_field_xor_value_fields(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "bad.yaml",
        """
        targets: [a]
        kind: cross_sheet
        source_sheet: ../parent
        key_field: id
        value_field: a
        value_fields:
          a: a
        """,
    )
    with pytest.raises(DerivationError):
        load_derivation(path)


def test_cross_sheet_multi_target_requires_value_fields(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "bad.yaml",
        """
        targets: [a, b]
        kind: cross_sheet
        source_sheet: ../parent
        key_field: id
        value_field: a
        """,
    )
    with pytest.raises(DerivationError, match="multi-target cross_sheet"):
        load_derivation(path)


# --- helpers --------------------------------------------------------------


def test_resolve_foreign_sheet_validates_target(tmp_path: Path) -> None:
    parent, child = _build_pair(tmp_path)
    resolved = resolve_foreign_sheet(child, "../parent")
    assert resolved == parent


def test_resolve_foreign_sheet_missing(tmp_path: Path) -> None:
    from folio.exceptions import FolioError

    sheet = tmp_path / "child"
    sheet.mkdir()
    with pytest.raises(FolioError, match="not found"):
        resolve_foreign_sheet(sheet, "../missing")


def test_foreign_records_hash_changes_with_content(tmp_path: Path) -> None:
    parent, child = _build_pair(tmp_path)
    h1 = foreign_records_hash(child, "../parent")

    (parent / "records.jsonl").write_text(
        '{"id": "p1", "industry": "Updated"}\n', encoding="utf-8"
    )
    h2 = foreign_records_hash(child, "../parent")
    assert h1 != h2


# --- execute_cross_sheet --------------------------------------------------


def test_execute_cross_sheet_match(tmp_path: Path) -> None:
    parent, child = _build_pair(tmp_path)
    derivation = CrossSheetDerivation.model_validate(
        {
            "targets": ["industry"],
            "kind": "cross_sheet",
            "source_sheet": "../parent",
            "key_field": "id",
            "value_field": "industry",
        }
    )
    values = execute_cross_sheet(derivation, "p1", sheet_path=child)
    assert values == {"industry": "Manufacturing"}


def test_execute_cross_sheet_no_match_returns_empty(tmp_path: Path) -> None:
    parent, child = _build_pair(tmp_path)
    derivation = CrossSheetDerivation.model_validate(
        {
            "targets": ["industry"],
            "kind": "cross_sheet",
            "source_sheet": "../parent",
            "key_field": "id",
            "value_field": "industry",
        }
    )
    values = execute_cross_sheet(derivation, "missing", sheet_path=child)
    assert values == {}


def test_execute_cross_sheet_multi_value(tmp_path: Path) -> None:
    parent, child = _build_pair(tmp_path)
    # Use an ad-hoc multi-target derivation reading the same column twice.
    derivation = CrossSheetDerivation.model_validate(
        {
            "targets": ["industry_alias", "industry_orig"],
            "kind": "cross_sheet",
            "source_sheet": "../parent",
            "key_field": "id",
            "value_fields": {
                "industry_alias": "industry",
                "industry_orig": "industry",
            },
        }
    )
    values = execute_cross_sheet(derivation, "p2", sheet_path=child)
    assert values == {
        "industry_alias": "Software",
        "industry_orig": "Software",
    }


# --- Sheet.materialize integration ---------------------------------------


def test_materialize_cross_sheet_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, child = _build_pair(tmp_path)
    monkeypatch.setattr(
        "folio._cache.default_cache_root",
        lambda sheet_id: tmp_path / "cache" / sheet_id,
    )

    sheet = open_sheet(child, actor="agent:cross")
    result = sheet.materialize()
    assert result["failures"] == []

    rows = sheet.query("SELECT id, industry FROM records ORDER BY id")
    # p3 has no parent match so it is skipped (no industry).
    assert rows == [
        {"id": "p1", "industry": "Manufacturing"},
        {"id": "p2", "industry": "Software"},
        {"id": "p3", "industry": None},
    ]
