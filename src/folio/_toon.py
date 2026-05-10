"""Thin TOON encoder for ``list_records``.

The format is a header line ``[N]{field1, field2, ...}:`` followed by
one body line per record. Cells whose JSON form is identical to their
plain string form pass through unquoted; anything else is JSON-encoded
so the consumer can recover the exact value.

This is the "self-implemented (thin)" TOON described in design
overview §20. Full conformance with the upstream toon-format/toon
specification is out of scope for Phase 3.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

EMPTY_TOON_HEADER = "[0]{}:"

_TRIVIAL_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_:.\-]*$")


def encode(records: Iterable[dict[str, Any]]) -> str:
    """Encode an iterable of records as a TOON document."""
    materialized = list(records)
    if not materialized:
        return EMPTY_TOON_HEADER

    field_order = _collect_field_order(materialized)
    header_fields = ", ".join(field_order)
    lines = [f"[{len(materialized)}]{{{header_fields}}}:"]

    for record in materialized:
        cells = [_encode_cell(record.get(field)) for field in field_order]
        lines.append(", ".join(cells))

    return "\n".join(lines)


# --- internal --------------------------------------------------------------


def _collect_field_order(records: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for record in records:
        for key in record:
            if key not in seen:
                seen[key] = None
    return list(seen.keys())


def _encode_cell(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _encode_float(value)
    if isinstance(value, str):
        if _is_trivial_string(value):
            return value
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _is_trivial_string(value: str) -> bool:
    if not value:
        return False
    if not _TRIVIAL_IDENT_RE.fullmatch(value):
        return False
    if value in {"null", "true", "false"}:
        return False
    return True


def _encode_float(value: float) -> str:
    if value != value or value in (float("inf"), float("-inf")):
        # Non-finite floats are not representable in JSON / TOON; emit JSON
        # which produces valid Python output via json.dumps -> Infinity / NaN
        # is rejected. Surface as a string so callers can spot it.
        raise ValueError(f"non-finite float in TOON output: {value}")
    text = repr(value)
    return text


__all__ = [
    "EMPTY_TOON_HEADER",
    "encode",
]
