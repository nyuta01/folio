"""Tests for the Phase 4 ``python`` extension kind."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from folio import open_sheet
from folio.derivation import DerivationError, load_derivation
from folio.kinds import PythonDerivation, execute_python


def _write_yaml(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return path


def _build_sheet(tmp_path: Path, script_body: str, *, extra_fields: str = "") -> Path:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            f"""
            apiVersion: v3.0.0
            kind: DataContract
            id: py-test-{tmp_path.name}
            name: py-test
            version: 1.0.0
            schema:
              - name: items
                physicalType: jsonl
                properties:
                  - name: id
                    logicalType: string
                    primaryKey: true
                    required: true
                  - name: company
                    logicalType: string
                  - name: tag
                    logicalType: string
                    x-derived: true
                    x-inputs: [company]
            {extra_fields}
            """
        ).strip(),
        encoding="utf-8",
    )
    (sheet / "records.jsonl").write_text(
        '{"id": "a", "company": "Acme"}\n', encoding="utf-8"
    )
    scripts = sheet / "scripts"
    scripts.mkdir()
    (scripts / "enrich.py").write_text(
        textwrap.dedent(script_body).strip() + "\n",
        encoding="utf-8",
    )
    return sheet


# --- Pydantic shape -------------------------------------------------------


def test_minimal_python_derivation_loads(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "tag.yaml",
        """
        targets: [tag]
        inputs: [company]
        kind: python
        script: enrich
        """,
    )
    derivation = load_derivation(path)
    assert isinstance(derivation, PythonDerivation)
    assert derivation.output == "text"


def test_python_multi_target_requires_output_schema(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "bad.yaml",
        """
        targets: [a, b]
        kind: python
        script: enrich
        output: json
        """,
    )
    with pytest.raises(DerivationError, match="output_schema"):
        load_derivation(path)


def test_python_single_target_must_not_declare_output_schema(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "bad.yaml",
        """
        targets: [a]
        kind: python
        script: enrich
        output: text
        output_schema:
          a: string
        """,
    )
    with pytest.raises(DerivationError):
        load_derivation(path)


# --- execute_python -------------------------------------------------------


def test_execute_python_text_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sheet = _build_sheet(
        tmp_path,
        """
        import sys, json
        inputs = json.loads(sys.argv[2])
        print(f"industry of {inputs['company']}")
        """,
    )
    monkeypatch.setattr(
        "folio.scripts.runtime_root_for_sheet",
        lambda sheet_id: tmp_path / "runtime" / sheet_id,
    )

    derivation = PythonDerivation.model_validate(
        {
            "targets": ["tag"],
            "inputs": ["company"],
            "kind": "python",
            "script": "enrich",
        }
    )

    values = execute_python(
        derivation,
        {"company": "Acme"},
        sheet_path=sheet,
        sheet_id="test-id",
    )

    assert values == {"tag": "industry of Acme"}


def test_execute_python_json_multi_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sheet = _build_sheet(
        tmp_path,
        """
        import sys, json
        inputs = json.loads(sys.argv[2])
        print(json.dumps({"a": inputs["company"].upper(), "b": "ok"}))
        """,
    )
    monkeypatch.setattr(
        "folio.scripts.runtime_root_for_sheet",
        lambda sheet_id: tmp_path / "runtime" / sheet_id,
    )

    derivation = PythonDerivation.model_validate(
        {
            "targets": ["a", "b"],
            "inputs": ["company"],
            "kind": "python",
            "script": "enrich",
            "output": "json",
            "output_schema": {"a": "string", "b": "string"},
        }
    )

    values = execute_python(
        derivation,
        {"company": "acme"},
        sheet_path=sheet,
        sheet_id="test-id",
    )

    assert values == {"a": "ACME", "b": "ok"}


def test_execute_python_failed_exit_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sheet = _build_sheet(
        tmp_path,
        """
        import sys
        sys.stderr.write("boom\\n")
        sys.exit(2)
        """,
    )
    monkeypatch.setattr(
        "folio.scripts.runtime_root_for_sheet",
        lambda sheet_id: tmp_path / "runtime" / sheet_id,
    )

    derivation = PythonDerivation.model_validate(
        {
            "targets": ["tag"],
            "inputs": [],
            "kind": "python",
            "script": "enrich",
        }
    )

    from folio.exceptions import FolioError

    with pytest.raises(FolioError, match="exited with 2"):
        execute_python(
            derivation,
            {},
            sheet_path=sheet,
            sheet_id="test-id",
        )


# --- Sheet.materialize integration ---------------------------------------


def test_materialize_python_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sheet = _build_sheet(
        tmp_path,
        """
        import sys, json
        inputs = json.loads(sys.argv[2])
        print(inputs["company"].upper())
        """,
    )
    derivations = sheet / "derivations"
    derivations.mkdir()
    (derivations / "tag.yaml").write_text(
        textwrap.dedent(
            """
            targets: [tag]
            inputs: [company]
            kind: python
            script: enrich
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "folio.scripts.runtime_root_for_sheet",
        lambda sheet_id: tmp_path / "runtime" / sheet_id,
    )
    monkeypatch.setattr(
        "folio._cache.default_cache_root",
        lambda sheet_id: tmp_path / "cache" / sheet_id,
    )

    s = open_sheet(sheet, actor="agent:py")
    result = s.materialize()
    assert result["materialized"] == 1
    assert result["failures"] == []

    rows = s.query("SELECT id, tag FROM records")
    assert rows == [{"id": "a", "tag": "ACME"}]
