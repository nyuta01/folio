"""Phase 4 Frictionless Data Package descriptor generator.

Maps a Folio ``Contract`` (ODCS subset) plus its ``records.jsonl`` into
a Frictionless v1 descriptor per §14.2 of the design overview. The
generator is pure: callers compose it with a writer to land
``datapackage.json`` under the sheet directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contract import Contract, LogicalType, Property, Schema, load_contract


LOGICAL_TO_FRICTIONLESS: dict[LogicalType, str] = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "date": "date",
    "timestamp": "datetime",
    "array": "array",
    "object": "object",
}


def build_descriptor(
    contract: Contract,
    *,
    records_path: str = "records.jsonl",
) -> dict[str, Any]:
    """Construct a Frictionless Data Package descriptor for ``contract``."""
    schema = contract.main_schema

    descriptor: dict[str, Any] = {
        "name": contract.id,
        "title": contract.name,
        "version": contract.version,
        "resources": [_build_resource(schema, records_path=records_path)],
    }
    if contract.description is not None:
        descriptor["description"] = contract.description
    return descriptor


def write_datapackage(
    sheet_path: str | Path,
    output_path: str | Path | None = None,
    *,
    records_path: str = "records.jsonl",
) -> Path:
    """Write the descriptor for ``sheet_path`` to ``datapackage.json``.

    Returns the path that was written.
    """
    contract = load_contract(sheet_path)
    descriptor = build_descriptor(contract, records_path=records_path)
    target = Path(output_path) if output_path else Path(sheet_path) / "datapackage.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(descriptor, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


# --- internal --------------------------------------------------------------


def _build_resource(schema: Schema, *, records_path: str) -> dict[str, Any]:
    fields = [_build_field(prop) for prop in schema.properties]
    schema_block: dict[str, Any] = {"fields": fields}
    primary = [prop.name for prop in schema.properties if prop.primary_key]
    if primary:
        schema_block["primaryKey"] = primary[0]
    return {
        "name": schema.name,
        "path": records_path,
        "format": "jsonl",
        "profile": "tabular-data-resource",
        "schema": schema_block,
    }


def _build_field(prop: Property) -> dict[str, Any]:
    field: dict[str, Any] = {
        "name": prop.name,
        "type": LOGICAL_TO_FRICTIONLESS[prop.logical_type],
    }
    if prop.description is not None:
        field["description"] = prop.description
    constraints: dict[str, Any] = {}
    if prop.required and not prop.derived:
        constraints["required"] = True
    if constraints:
        field["constraints"] = constraints
    if prop.derived:
        field["folioDerived"] = True
    return field


__all__ = [
    "LOGICAL_TO_FRICTIONLESS",
    "build_descriptor",
    "write_datapackage",
]
