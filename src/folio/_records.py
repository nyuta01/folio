"""JSONL read/write helpers for ``records.jsonl``.

Atomic writes use a temp file + ``os.replace`` so a partially-written file
cannot replace the canonical records file (§12 of the design overview).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .exceptions import RecordsError


def read_records(path: Path) -> list[dict[str, Any]]:
    """Read ``records.jsonl`` line by line. Returns ``[]`` for missing or empty files."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RecordsError(
                f"records.jsonl line {line_number}: invalid JSON ({exc.msg})"
            ) from exc
        if not isinstance(value, dict):
            raise RecordsError(
                f"records.jsonl line {line_number}: each record must be a JSON object"
            )
        records.append(value)
    return records


def atomic_write_records(path: Path, records: Iterable[dict[str, Any]]) -> None:
    """Write ``records`` to ``path`` atomically via temp file + ``os.replace``.

    The file is fsynced before the rename so a crash between write and rename
    cannot leave a corrupt records file.
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_str = tempfile.mkstemp(
        dir=parent, prefix=".records.", suffix=".jsonl.tmp"
    )
    tmp_path = Path(tmp_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
