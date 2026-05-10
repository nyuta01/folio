"""Tests for ``folio.datapackage`` (Phase 4 Frictionless export)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from folio.cli import app
from folio.contract import load_contract
from folio.datapackage import (
    LOGICAL_TO_FRICTIONLESS,
    build_descriptor,
    write_datapackage,
)


def _write_contract(sheet: Path, body: str) -> None:
    sheet.mkdir(parents=True, exist_ok=True)
    (sheet / "contract.yaml").write_text(textwrap.dedent(body).strip(), encoding="utf-8")
    (sheet / "records.jsonl").write_text("", encoding="utf-8")


@pytest.fixture
def rich_sheet(tmp_path: Path) -> Path:
    sheet = tmp_path / "sheet"
    _write_contract(
        sheet,
        """
        apiVersion: v3.0.0
        kind: DataContract
        id: dp-test
        name: dp-test
        version: 1.0.0
        description: A test sheet for datapackage export.
        schema:
          - name: items
            physicalType: jsonl
            properties:
              - name: id
                logicalType: string
                primaryKey: true
                required: true
                description: Stable id
              - name: count
                logicalType: integer
                required: true
              - name: amount
                logicalType: number
              - name: active
                logicalType: boolean
              - name: created_at
                logicalType: timestamp
              - name: birthday
                logicalType: date
              - name: tags
                logicalType: array
              - name: metadata
                logicalType: object
              - name: industry_tag
                logicalType: string
                x-derived: true
                x-inputs: [count]
        """,
    )
    return sheet


# --- mapping --------------------------------------------------------------


def test_logical_to_frictionless_covers_every_logical_type() -> None:
    expected = {
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "date": "date",
        "timestamp": "datetime",
        "array": "array",
        "object": "object",
    }
    assert LOGICAL_TO_FRICTIONLESS == expected


# --- build_descriptor -----------------------------------------------------


def test_build_descriptor_top_level_metadata(rich_sheet: Path) -> None:
    contract = load_contract(rich_sheet)
    descriptor = build_descriptor(contract)
    assert descriptor["name"] == "dp-test"
    assert descriptor["title"] == "dp-test"
    assert descriptor["version"] == "1.0.0"
    assert descriptor["description"] == "A test sheet for datapackage export."
    assert isinstance(descriptor["resources"], list)
    assert len(descriptor["resources"]) == 1


def test_build_descriptor_resource_shape(rich_sheet: Path) -> None:
    descriptor = build_descriptor(load_contract(rich_sheet))
    resource = descriptor["resources"][0]
    assert resource["name"] == "items"
    assert resource["path"] == "records.jsonl"
    assert resource["format"] == "jsonl"
    assert resource["schema"]["primaryKey"] == "id"


def test_build_descriptor_field_types(rich_sheet: Path) -> None:
    descriptor = build_descriptor(load_contract(rich_sheet))
    fields = {field["name"]: field for field in descriptor["resources"][0]["schema"]["fields"]}
    assert fields["id"]["type"] == "string"
    assert fields["count"]["type"] == "integer"
    assert fields["amount"]["type"] == "number"
    assert fields["active"]["type"] == "boolean"
    assert fields["created_at"]["type"] == "datetime"
    assert fields["birthday"]["type"] == "date"
    assert fields["tags"]["type"] == "array"
    assert fields["metadata"]["type"] == "object"


def test_build_descriptor_propagates_descriptions(rich_sheet: Path) -> None:
    fields = {
        field["name"]: field
        for field in build_descriptor(load_contract(rich_sheet))["resources"][0]["schema"]["fields"]
    }
    assert fields["id"]["description"] == "Stable id"
    assert "description" not in fields["count"]


def test_build_descriptor_marks_required_constraints(rich_sheet: Path) -> None:
    fields = {
        field["name"]: field
        for field in build_descriptor(load_contract(rich_sheet))["resources"][0]["schema"]["fields"]
    }
    assert fields["id"]["constraints"] == {"required": True}
    assert fields["count"]["constraints"] == {"required": True}
    assert "constraints" not in fields["amount"]


def test_build_descriptor_flags_derived_fields(rich_sheet: Path) -> None:
    fields = {
        field["name"]: field
        for field in build_descriptor(load_contract(rich_sheet))["resources"][0]["schema"]["fields"]
    }
    assert fields["industry_tag"]["folioDerived"] is True
    assert "constraints" not in fields["industry_tag"]


def test_build_descriptor_omits_description_when_absent(tmp_path: Path) -> None:
    sheet = tmp_path / "no-desc"
    _write_contract(
        sheet,
        """
        apiVersion: v3.0.0
        kind: DataContract
        id: no-desc
        name: no-desc
        version: 1.0.0
        schema:
          - name: items
            physicalType: jsonl
            properties:
              - name: id
                logicalType: string
                primaryKey: true
                required: true
        """,
    )
    descriptor = build_descriptor(load_contract(sheet))
    assert "description" not in descriptor


# --- write_datapackage ---------------------------------------------------


def test_write_datapackage_default_target(rich_sheet: Path) -> None:
    target = write_datapackage(rich_sheet)
    assert target == rich_sheet / "datapackage.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["name"] == "dp-test"


def test_write_datapackage_custom_target(rich_sheet: Path, tmp_path: Path) -> None:
    out = tmp_path / "elsewhere" / "package.json"
    target = write_datapackage(rich_sheet, out)
    assert target == out
    assert out.is_file()


# --- CLI -----------------------------------------------------------------


def test_cli_export_datapackage_to_stdout(rich_sheet: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app, ["export", "datapackage", str(rich_sheet), "--stdout"]
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["name"] == "dp-test"


def test_cli_export_datapackage_writes_file(rich_sheet: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "export",
            "datapackage",
            str(rich_sheet),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert "wrote" in result.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["name"] == "dp-test"
