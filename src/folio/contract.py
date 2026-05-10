"""Pydantic v2 models for Folio ``contract.yaml``.

The contract format is a subset-compatible with ODCS (Open Data Contract
Standard). The canonical specification lives at
``docs/design-docs/overview.md`` §6.

This module is deliberately read-only: it loads YAML, validates the structural
invariants required by Phase 0, and exposes a typed object graph that other
parts of the SDK can consume.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from typing_extensions import Self

from .exceptions import ContractError

LogicalType = Literal[
    "string",
    "integer",
    "number",
    "boolean",
    "date",
    "timestamp",
    "array",
    "object",
]

ContractKind = Literal["DataContract"]


class Property(BaseModel):
    """A single field declaration on a sheet's schema."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    logical_type: LogicalType = Field(alias="logicalType")
    primary_key: bool = Field(default=False, alias="primaryKey")
    required: bool = False
    description: str | None = None
    derived: bool = Field(default=False, alias="x-derived")
    inputs: list[str] = Field(default_factory=list, alias="x-inputs")
    editable_by: list[str] | None = Field(default=None, alias="x-editable-by")


class Schema(BaseModel):
    """The single schema element of a Folio contract (1 sheet = 1 model)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    physical_type: str = Field(default="jsonl", alias="physicalType")
    properties: list[Property] = Field(min_length=1)


class Contract(BaseModel):
    """Top-level ``contract.yaml`` document."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    api_version: str = Field(alias="apiVersion")
    kind: ContractKind
    id: str
    name: str
    version: str
    description: str | None = None
    schemas: list[Schema] = Field(alias="schema", min_length=1, max_length=1)

    @property
    def main_schema(self) -> Schema:
        """The single schema element. ``1 sheet = 1 model`` per the spec."""
        return self.schemas[0]

    @model_validator(mode="after")
    def _validate_schema_invariants(self) -> Self:
        schema = self.main_schema

        names = [prop.name for prop in schema.properties]
        duplicates = sorted(
            name for name, count in Counter(names).items() if count > 1
        )
        if duplicates:
            raise ValueError(
                f"schema {schema.name!r} has duplicate property names: {duplicates}"
            )

        primary_keys = [prop.name for prop in schema.properties if prop.primary_key]
        if len(primary_keys) > 1:
            raise ValueError(
                f"schema {schema.name!r} declares multiple primaryKey properties: "
                f"{primary_keys}"
            )

        unknown_inputs: list[tuple[str, str]] = []
        property_names = set(names)
        for prop in schema.properties:
            if not prop.derived:
                continue
            for input_name in prop.inputs:
                if input_name not in property_names:
                    unknown_inputs.append((prop.name, input_name))
        if unknown_inputs:
            joined = ", ".join(f"{p}<-{i}" for p, i in unknown_inputs)
            raise ValueError(f"derived fields reference unknown inputs: {joined}")

        return self


def write_contract(sheet_path: str | Path, contract: Contract) -> None:
    """Atomically rewrite ``contract.yaml`` from a validated ``Contract``.

    The contract is re-validated through Pydantic before serialization, so
    callers can mutate the model in memory and rely on this to refuse
    invalid intermediate states. Comments in the original file are not
    preserved — Folio owns the file format.
    """
    target = Path(sheet_path) / "contract.yaml"
    payload = contract.model_dump(mode="json", by_alias=True, exclude_defaults=False)
    # Drop fields that default to falsy / empty so the on-disk YAML stays compact.
    for prop in payload["schema"][0]["properties"]:
        if prop.get("primaryKey") is False:
            prop.pop("primaryKey", None)
        if prop.get("required") is False:
            prop.pop("required", None)
        if prop.get("x-derived") is False:
            prop.pop("x-derived", None)
        if prop.get("x-inputs") == []:
            prop.pop("x-inputs", None)
        if prop.get("x-editable-by") in (None, []):
            prop.pop("x-editable-by", None)
        if prop.get("description") is None:
            prop.pop("description", None)
    if payload.get("description") is None:
        payload.pop("description", None)
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    tmp = target.with_suffix(".yaml.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(target)


def load_contract(sheet_path: str | Path) -> Contract:
    """Load and validate ``<sheet_path>/contract.yaml``.

    Raises:
        ContractError: when the file is missing, the YAML cannot be parsed,
            or the document violates a Phase 0 invariant.
    """
    contract_path = Path(sheet_path) / "contract.yaml"
    if not contract_path.is_file():
        raise ContractError(f"contract.yaml not found at {contract_path}")

    try:
        raw: Any = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContractError(f"contract.yaml is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ContractError("contract.yaml top-level value must be a mapping")

    try:
        return Contract.model_validate(raw)
    except ValidationError as exc:
        raise ContractError(f"contract.yaml is not valid: {exc}") from exc
