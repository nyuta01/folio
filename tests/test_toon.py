"""Tests for ``folio._toon`` (Phase 3 TOON encoder)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from folio import open_sheet
from folio._toon import EMPTY_TOON_HEADER, encode
from folio.cli import app


# --- encode ---------------------------------------------------------------


def test_encode_empty_list_returns_empty_header() -> None:
    assert encode([]) == EMPTY_TOON_HEADER


def test_encode_single_scalar_record() -> None:
    out = encode([{"id": "cust_001", "n": 1}])
    assert out == "[1]{id, n}:\ncust_001, 1"


def test_encode_unquotes_trivial_strings_and_quotes_non_trivial() -> None:
    out = encode(
        [
            {"id": "cust_001", "name": "Acme Inc"},
            {"id": "cust_002", "name": "DataFlow"},
        ]
    )
    lines = out.split("\n")
    assert lines[0] == "[2]{id, name}:"
    assert lines[1] == 'cust_001, "Acme Inc"'  # space → JSON-encoded
    assert lines[2] == "cust_002, DataFlow"  # trivial → unquoted


def test_encode_handles_null_bool_int_float() -> None:
    out = encode(
        [
            {"a": None, "b": True, "c": False, "d": 42, "e": 3.5},
        ]
    )
    lines = out.split("\n")
    assert lines[0] == "[1]{a, b, c, d, e}:"
    assert lines[1] == "null, true, false, 42, 3.5"


def test_encode_strings_that_collide_with_keywords_are_quoted() -> None:
    # The literal string "null" must round-trip as a string, not a null.
    out = encode([{"v": "null"}])
    assert out == '[1]{v}:\n"null"'


def test_encode_nested_objects_and_arrays_are_json_encoded() -> None:
    out = encode(
        [
            {"id": "x", "tags": ["a", "b"], "meta": {"k": 1}},
        ]
    )
    assert out == '[1]{id, tags, meta}:\nx, ["a", "b"], {"k": 1}'


def test_encode_field_order_is_first_appearance() -> None:
    out = encode(
        [
            {"a": 1, "b": 2},
            {"c": 3, "a": 4},
        ]
    )
    assert out.startswith("[2]{a, b, c}:")


def test_encode_missing_field_emits_null() -> None:
    out = encode(
        [
            {"a": 1, "b": 2},
            {"a": 3},
        ]
    )
    lines = out.split("\n")
    assert lines[2] == "3, null"


def test_encode_string_with_comma_or_quote_is_json_encoded() -> None:
    out = encode([{"v": 'a, "b"'}])
    cells = out.split("\n")[1]
    # JSON dump escapes the embedded quotes.
    assert cells == '"a, \\"b\\""'


# --- Sheet.list_records integration --------------------------------------


def test_list_records_format_toon_returns_toon_string(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    result = sheet.list_records(fields=["id", "title"], format="toon", limit=10)

    assert result["format"] == "toon"
    assert result["next_cursor"] is None
    assert isinstance(result["records"], str)
    text = result["records"]
    assert text.startswith("[3]{id, title}:")


def test_list_records_format_json_default(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    result = sheet.list_records(limit=10)
    assert result["format"] == "json"
    assert isinstance(result["records"], list)


def test_list_records_rejects_unknown_format(populated_sheet: Path) -> None:
    from folio.exceptions import OperationError

    sheet = open_sheet(populated_sheet)
    with pytest.raises(OperationError, match="format"):
        sheet.list_records(format="csv")


# --- CLI integration -----------------------------------------------------


def test_cli_list_format_toon_emits_envelope_with_toon_records(
    populated_sheet: Path,
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["list", str(populated_sheet), "--format", "toon", "--fields", "id"],
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["format"] == "toon"
    assert isinstance(payload["records"], str)
    assert payload["records"].startswith("[3]{id}:")
