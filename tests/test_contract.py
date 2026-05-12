"""Tests for ``folio.contract`` (Phase 0 contract.yaml validation)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from folio import ContractError, load_contract, open_sheet

MINIMAL_CONTRACT = textwrap.dedent(
    """
    apiVersion: v3.0.0
    kind: DataContract
    id: minimal
    name: minimal
    version: 1.0.0
    schema:
      - name: items
        physicalType: jsonl
        properties:
          - name: id
            logicalType: string
            primaryKey: true
            required: true
          - name: title
            logicalType: string
            required: true
    """
).strip()


def write_sheet(tmp_path: Path, contract_text: str) -> Path:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(contract_text, encoding="utf-8")
    (sheet / "records.jsonl").write_text("", encoding="utf-8")
    return sheet


def test_minimal_contract_loads(tmp_path: Path) -> None:
    sheet = write_sheet(tmp_path, MINIMAL_CONTRACT)

    contract = load_contract(sheet)

    assert contract.id == "minimal"
    assert contract.kind == "DataContract"
    assert contract.api_version == "v3.0.0"
    assert len(contract.schemas) == 1
    assert contract.main_schema.name == "items"
    assert [prop.name for prop in contract.main_schema.properties] == ["id", "title"]
    assert contract.main_schema.properties[0].primary_key is True


def test_contract_write_ignores_predictable_tmp_symlink(tmp_path: Path) -> None:
    sheet = write_sheet(tmp_path, MINIMAL_CONTRACT)
    victim = tmp_path / "victim_config"
    victim.write_text("ORIGINAL_SECRET_CONFIG=keepme\n", encoding="utf-8")
    predictable_tmp = sheet / "contract.yaml.tmp"
    try:
        predictable_tmp.symlink_to(victim)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    open_sheet(sheet, actor="agent:test").add_property(
        {"name": "notes", "logicalType": "string"}, actor="agent:test"
    )

    assert victim.read_text(encoding="utf-8") == "ORIGINAL_SECRET_CONFIG=keepme\n"
    assert predictable_tmp.is_symlink()
    assert predictable_tmp.readlink() == victim
    assert not (sheet / "contract.yaml").is_symlink()
    assert "name: notes" in (sheet / "contract.yaml").read_text(encoding="utf-8")


def test_missing_contract_yaml_raises(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="contract.yaml not found"):
        load_contract(tmp_path)


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text("not: valid: yaml:\n", encoding="utf-8")

    with pytest.raises(ContractError, match="not valid YAML"):
        load_contract(sheet)


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    sheet = write_sheet(tmp_path, "- one\n- two\n")

    with pytest.raises(ContractError, match="top-level value must be a mapping"):
        load_contract(sheet)


def test_multiple_schemas_rejected(tmp_path: Path) -> None:
    contract_yaml = MINIMAL_CONTRACT + textwrap.dedent(
        """
          - name: extras
            physicalType: jsonl
            properties:
              - name: x
                logicalType: string
        """
    )
    sheet = write_sheet(tmp_path, contract_yaml)

    with pytest.raises(ContractError):
        load_contract(sheet)


def test_multiple_primary_keys_rejected(tmp_path: Path) -> None:
    contract_yaml = textwrap.dedent(
        """
        apiVersion: v3.0.0
        kind: DataContract
        id: bad
        name: bad
        version: 1.0.0
        schema:
          - name: items
            physicalType: jsonl
            properties:
              - name: id
                logicalType: string
                primaryKey: true
              - name: alt
                logicalType: string
                primaryKey: true
        """
    ).strip()
    sheet = write_sheet(tmp_path, contract_yaml)

    with pytest.raises(ContractError, match="multiple primaryKey"):
        load_contract(sheet)


def test_invalid_logical_type_rejected(tmp_path: Path) -> None:
    contract_yaml = textwrap.dedent(
        """
        apiVersion: v3.0.0
        kind: DataContract
        id: bad
        name: bad
        version: 1.0.0
        schema:
          - name: items
            physicalType: jsonl
            properties:
              - name: id
                logicalType: bigint
                primaryKey: true
        """
    ).strip()
    sheet = write_sheet(tmp_path, contract_yaml)

    with pytest.raises(ContractError):
        load_contract(sheet)


def test_derived_field_with_known_inputs_loads(tmp_path: Path) -> None:
    contract_yaml = textwrap.dedent(
        """
        apiVersion: v3.0.0
        kind: DataContract
        id: derived
        name: derived
        version: 1.0.0
        schema:
          - name: items
            physicalType: jsonl
            properties:
              - name: id
                logicalType: string
                primaryKey: true
              - name: company_name
                logicalType: string
              - name: industry_tag
                logicalType: string
                description: A single-word industry tag
                x-derived: true
                x-inputs: [company_name]
                x-editable-by: ["agent:*", "human:*"]
        """
    ).strip()
    sheet = write_sheet(tmp_path, contract_yaml)

    contract = load_contract(sheet)

    industry = next(
        prop for prop in contract.main_schema.properties if prop.name == "industry_tag"
    )
    assert industry.derived is True
    assert industry.inputs == ["company_name"]
    assert industry.editable_by == ["agent:*", "human:*"]


def test_derived_field_with_unknown_input_rejected(tmp_path: Path) -> None:
    contract_yaml = textwrap.dedent(
        """
        apiVersion: v3.0.0
        kind: DataContract
        id: bad
        name: bad
        version: 1.0.0
        schema:
          - name: items
            physicalType: jsonl
            properties:
              - name: id
                logicalType: string
                primaryKey: true
              - name: industry_tag
                logicalType: string
                x-derived: true
                x-inputs: [does_not_exist]
        """
    ).strip()
    sheet = write_sheet(tmp_path, contract_yaml)

    with pytest.raises(ContractError, match="unknown inputs"):
        load_contract(sheet)


def test_duplicate_property_names_rejected(tmp_path: Path) -> None:
    contract_yaml = textwrap.dedent(
        """
        apiVersion: v3.0.0
        kind: DataContract
        id: bad
        name: bad
        version: 1.0.0
        schema:
          - name: items
            physicalType: jsonl
            properties:
              - name: id
                logicalType: string
                primaryKey: true
              - name: id
                logicalType: string
        """
    ).strip()
    sheet = write_sheet(tmp_path, contract_yaml)

    with pytest.raises(ContractError, match="duplicate"):
        load_contract(sheet)


def test_extra_property_attribute_rejected(tmp_path: Path) -> None:
    contract_yaml = textwrap.dedent(
        """
        apiVersion: v3.0.0
        kind: DataContract
        id: bad
        name: bad
        version: 1.0.0
        schema:
          - name: items
            physicalType: jsonl
            properties:
              - name: id
                logicalType: string
                primaryKey: true
                unknown_attr: nope
        """
    ).strip()
    sheet = write_sheet(tmp_path, contract_yaml)

    with pytest.raises(ContractError):
        load_contract(sheet)
