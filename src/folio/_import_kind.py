"""Import-kind execution helpers for Phase 1.

Loads source rows from CSV / JSONL / JSON files relative to a sheet
directory and computes per-record target values for an
``ImportDerivation``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .derivation import ImportDerivation
from .exceptions import FolioError


class ImportSourceError(FolioError):
    """Raised when an import-kind source file is missing or malformed."""


SUPPORTED_EXTENSIONS = (".csv", ".jsonl", ".json")


def load_import_source(sheet_path: Path, source: str) -> list[dict[str, Any]]:
    """Load ``source`` (relative to ``sheet_path``) into a list of row dicts."""
    src_path = (Path(sheet_path) / source).resolve()
    sheet_root = Path(sheet_path).resolve()
    try:
        src_path.relative_to(sheet_root)
    except ValueError as exc:
        raise ImportSourceError(
            f"import source must live under the sheet directory: {source}"
        ) from exc
    if not src_path.is_file():
        raise ImportSourceError(f"import source not found: {src_path}")

    suffix = src_path.suffix.lower()
    if suffix == ".csv":
        return _load_csv(src_path)
    if suffix == ".jsonl":
        return _load_jsonl(src_path)
    if suffix == ".json":
        return _load_json(src_path)
    raise ImportSourceError(
        f"unsupported import source extension {suffix!r}; "
        f"supported: {SUPPORTED_EXTENSIONS}"
    )


def apply_import(
    derivation: ImportDerivation,
    source_rows: list[dict[str, Any]],
    primary_key_value: Any,
) -> dict[str, Any]:
    """Compute ``{target_field: value}`` for one record's primary key.

    Returns an empty dict when no source row matches.
    """
    matches = [
        row
        for row in source_rows
        if row.get(derivation.key_field) == primary_key_value
    ]
    if not matches:
        return {}
    if len(matches) > 1:
        raise ImportSourceError(
            f"import source has {len(matches)} rows where "
            f"{derivation.key_field}={primary_key_value!r}; expected at most 1"
        )

    matched = matches[0]
    if derivation.value_field is not None:
        return {derivation.targets[0]: matched.get(derivation.value_field)}

    assert derivation.value_fields is not None  # validated by Pydantic
    return {
        target: matched.get(source_field)
        for target, source_field in derivation.value_fields.items()
    }


# --- internal --------------------------------------------------------------


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
    return rows


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ImportSourceError(
                f"{path} line {line_number}: invalid JSON ({exc.msg})"
            ) from exc
        if not isinstance(value, dict):
            raise ImportSourceError(
                f"{path} line {line_number}: each row must be a JSON object"
            )
        rows.append(value)
    return rows


def _load_json(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImportSourceError(f"{path}: invalid JSON ({exc.msg})") from exc
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ImportSourceError(f"{path}: must be a JSON list of objects")
    return data


__all__ = [
    "ImportSourceError",
    "SUPPORTED_EXTENSIONS",
    "apply_import",
    "load_import_source",
]
