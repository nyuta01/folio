"""Tests for the Phase 4 ``sql`` extension kind."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from folio import open_sheet
from folio.derivation import DerivationError, load_derivation
from folio.kinds import SQLDerivation, execute_sql


def _write_yaml(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return path


# --- Pydantic shape -------------------------------------------------------


def test_minimal_sql_derivation_loads(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "tag.yaml",
        """
        targets: [tag]
        inputs: []
        kind: sql
        expression: "SELECT 1 AS only"
        """,
    )
    derivation = load_derivation(path)
    assert isinstance(derivation, SQLDerivation)
    assert derivation.expression.startswith("SELECT")


def test_sql_select_only_enforced(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "bad.yaml",
        """
        targets: [tag]
        kind: sql
        expression: "DELETE FROM records"
        """,
    )
    with pytest.raises(DerivationError):
        load_derivation(path)


def test_sql_multi_target_requires_output_schema(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "bad.yaml",
        """
        targets: [a, b]
        kind: sql
        expression: "SELECT a, b FROM records LIMIT 1"
        """,
    )
    with pytest.raises(DerivationError, match="output_schema"):
        load_derivation(path)


def test_sql_single_target_must_not_declare_output_schema(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "bad.yaml",
        """
        targets: [a]
        kind: sql
        expression: "SELECT 1 AS a"
        output_schema:
          a: integer
        """,
    )
    with pytest.raises(DerivationError):
        load_derivation(path)


# --- Execution + integration ---------------------------------------------


@pytest.fixture
def sql_sheet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            """
            apiVersion: v3.0.0
            kind: DataContract
            id: sql-test-{uid}
            name: sql-test
            version: 1.0.0
            schema:
              - name: items
                physicalType: jsonl
                properties:
                  - name: id
                    logicalType: string
                    primaryKey: true
                    required: true
                  - name: count
                    logicalType: integer
                  - name: total
                    logicalType: integer
                    x-derived: true
            """
        )
        .strip()
        .replace("{uid}", tmp_path.name),
        encoding="utf-8",
    )
    (sheet / "records.jsonl").write_text(
        '{"id": "a", "count": 1}\n'
        '{"id": "b", "count": 2}\n'
        '{"id": "c", "count": 3}\n',
        encoding="utf-8",
    )
    derivations = sheet / "derivations"
    derivations.mkdir()
    (derivations / "total.yaml").write_text(
        textwrap.dedent(
            """
            targets: [total]
            inputs: []
            kind: sql
            expression: "SELECT SUM(count) AS total FROM records"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "folio._cache.default_cache_root",
        lambda sheet_id: tmp_path / "cache" / sheet_id,
    )
    return sheet


def test_execute_sql_aggregates_records(sql_sheet: Path) -> None:
    sheet = open_sheet(sql_sheet)
    derivation = SQLDerivation.model_validate(
        {
            "targets": ["total"],
            "kind": "sql",
            "expression": "SELECT SUM(count) AS total FROM records",
        }
    )

    values = execute_sql(
        derivation,
        inputs={},
        contract=sheet.contract,
        records_path=sheet.records_path,
    )

    assert values == {"total": 6}


def test_materialize_sql_populates_records(sql_sheet: Path) -> None:
    sheet = open_sheet(sql_sheet, actor="agent:test")
    result = sheet.materialize()
    assert result["materialized"] == 3
    assert result["failures"] == []

    rows = sheet.query("SELECT id, total FROM records ORDER BY id")
    assert rows == [
        {"id": "a", "total": 6},
        {"id": "b", "total": 6},
        {"id": "c", "total": 6},
    ]


def test_sql_with_parameter_binding(sql_sheet: Path) -> None:
    sheet = open_sheet(sql_sheet)
    derivation = SQLDerivation.model_validate(
        {
            "targets": ["count"],
            "inputs": ["id"],
            "kind": "sql",
            "expression": "SELECT count FROM records WHERE id = ?",
        }
    )

    values = execute_sql(
        derivation,
        inputs={"id": "b"},
        contract=sheet.contract,
        records_path=sheet.records_path,
    )

    assert values == {"count": 2}
