"""``cross_sheet`` extension kind.

Reads values from a sibling sheet's ``records.jsonl``. The foreign
sheet is resolved by relative path; the current record's primary key
selects the row to read. The foreign records-file hash folds into the
materialize cache key so a foreign change invalidates downstream
derivations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, model_validator
from typing_extensions import Self

from .._cache import sha256_file
from .._records import read_records
from ..derivation import _BaseDerivation
from ..exceptions import FolioError


class CrossSheetDerivation(_BaseDerivation):
    """A derivation whose value comes from another sheet's records."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["cross_sheet"]
    source_sheet: str
    key_field: str
    value_field: str | None = None
    value_fields: dict[str, str] | None = None

    @model_validator(mode="after")
    def _validate_cross_sheet(self) -> Self:
        single_value = self.value_field is not None
        multi_value = self.value_fields is not None
        if single_value and multi_value:
            raise ValueError(
                "cross_sheet derivation must specify exactly one of "
                "'value_field' or 'value_fields'"
            )
        if not single_value and not multi_value:
            raise ValueError(
                "cross_sheet derivation must specify either 'value_field' "
                "or 'value_fields'"
            )
        if len(self.targets) == 1:
            if multi_value and self.value_fields is not None and (
                set(self.value_fields.keys()) != set(self.targets)
            ):
                raise ValueError(
                    "single-target cross_sheet 'value_fields' keys must equal targets"
                )
        else:
            if single_value:
                raise ValueError(
                    "multi-target cross_sheet derivation must use 'value_fields'"
                )
            if (
                self.value_fields is None
                or set(self.value_fields.keys()) != set(self.targets)
            ):
                raise ValueError(
                    "multi-target cross_sheet 'value_fields' keys must equal targets"
                )
        return self


def resolve_foreign_sheet(sheet_path: Path | str, source_sheet: str) -> Path:
    target = (Path(sheet_path) / source_sheet).resolve()
    if not target.is_dir():
        raise FolioError(f"cross_sheet source not found: {target}")
    if not (target / "records.jsonl").exists():
        raise FolioError(
            f"cross_sheet source missing records.jsonl: {target}"
        )
    return target


def foreign_records_hash(sheet_path: Path | str, source_sheet: str) -> str:
    """SHA-256 of the foreign records.jsonl file (or 'empty' when missing)."""
    target = resolve_foreign_sheet(sheet_path, source_sheet)
    records_path = target / "records.jsonl"
    if records_path.stat().st_size == 0:
        return "empty"
    return sha256_file(records_path)


def execute_cross_sheet(
    derivation: CrossSheetDerivation,
    primary_key_value: Any,
    *,
    sheet_path: Path | str,
) -> dict[str, Any]:
    """Resolve the foreign sheet's matching row and return the value map."""
    target = resolve_foreign_sheet(sheet_path, derivation.source_sheet)
    foreign_records = read_records(target / "records.jsonl")
    matches = [
        row
        for row in foreign_records
        if row.get(derivation.key_field) == primary_key_value
    ]
    if not matches:
        return {}
    if len(matches) > 1:
        raise FolioError(
            f"cross_sheet source has {len(matches)} rows where "
            f"{derivation.key_field}={primary_key_value!r}; expected at most 1"
        )

    matched = matches[0]
    if derivation.value_field is not None:
        return {derivation.targets[0]: matched.get(derivation.value_field)}

    assert derivation.value_fields is not None  # validated by Pydantic
    return {
        target_field: matched.get(source_field)
        for target_field, source_field in derivation.value_fields.items()
    }


__all__ = [
    "CrossSheetDerivation",
    "execute_cross_sheet",
    "foreign_records_hash",
    "resolve_foreign_sheet",
]
