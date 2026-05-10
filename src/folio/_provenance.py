"""Phase 1 ``provenance.jsonl`` append-only helpers.

Schema follows §9.1 of the design overview. The latest entry per
``(record_id, field)`` resolves the current source on read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exceptions import FolioError

REQUIRED_FIELDS = ("record_id", "field", "source", "actor", "at")
ALLOWED_SOURCES_HINT = ("ai", "import", "human_override")


class ProvenanceError(FolioError):
    """Raised when ``provenance.jsonl`` is malformed or an entry is invalid."""


def provenance_path(sheet_path: Path | str) -> Path:
    return Path(sheet_path) / "provenance.jsonl"


def append_provenance(sheet_path: Path | str, entry: dict[str, Any]) -> None:
    """Append one validated entry to ``provenance.jsonl``.

    The write opens with ``"a"`` mode (``O_APPEND``), so concurrent appends
    by independent writers are atomic for entries shorter than ``PIPE_BUF``
    (§12 of the design overview).
    """
    for field_name in REQUIRED_FIELDS:
        if field_name not in entry or entry[field_name] in (None, ""):
            raise ProvenanceError(
                f"provenance entry missing required field {field_name!r}"
            )

    line = json.dumps(entry, ensure_ascii=False) + "\n"
    path = provenance_path(sheet_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def read_provenance(sheet_path: Path | str) -> list[dict[str, Any]]:
    """Read every entry from ``provenance.jsonl`` in append order."""
    path = provenance_path(sheet_path)
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProvenanceError(
                f"provenance.jsonl line {line_number}: invalid JSON ({exc.msg})"
            ) from exc
        if not isinstance(value, dict):
            raise ProvenanceError(
                f"provenance.jsonl line {line_number}: each entry must be a JSON object"
            )
        entries.append(value)
    return entries


def latest_provenance(
    sheet_path: Path | str,
    record_id: str,
    field: str,
) -> dict[str, Any] | None:
    """Return the most recent entry for ``(record_id, field)`` or ``None``."""
    entries = read_provenance(sheet_path)
    for entry in reversed(entries):
        if entry.get("record_id") == record_id and entry.get("field") == field:
            return entry
    return None


def field_history(
    sheet_path: Path | str,
    record_id: str,
    field: str,
) -> list[dict[str, Any]]:
    """Return every entry for ``(record_id, field)`` in append order."""
    return [
        entry
        for entry in read_provenance(sheet_path)
        if entry.get("record_id") == record_id and entry.get("field") == field
    ]


def is_stale(latest_entry: dict[str, Any] | None, current_input_hash: str) -> bool:
    """Return ``True`` when the latest provenance hash differs from ``current_input_hash``.

    A missing entry is considered stale (the field has never been
    materialized). ``human_override`` skipping is the caller's decision
    (it depends on ``materialization.respect_human_override``); this
    helper concerns itself only with hash drift.
    """
    if latest_entry is None:
        return True
    return latest_entry.get("input_hash") != current_input_hash


__all__ = [
    "ALLOWED_SOURCES_HINT",
    "ProvenanceError",
    "append_provenance",
    "field_history",
    "is_stale",
    "latest_provenance",
    "provenance_path",
    "read_provenance",
]
