"""Tests for ``folio._provenance`` (Phase 1 provenance.jsonl helpers)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from folio._provenance import (
    ProvenanceError,
    append_provenance,
    field_history,
    is_stale,
    latest_provenance,
    provenance_path,
    read_provenance,
)


def _entry(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "record_id": "cust_001",
        "field": "industry_tag",
        "source": "ai",
        "actor": "agent:enrichment-bot",
        "at": "2026-05-09T10:00:00Z",
        "input_hash": "sha256:" + ("a" * 64),
        "model": "claude-sonnet-4-6",
        "cost_usd": 0.0008,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def sheet(tmp_path: Path) -> Path:
    sheet_dir = tmp_path / "sheet"
    sheet_dir.mkdir()
    return sheet_dir


# --- append + read ---------------------------------------------------------


def test_read_provenance_returns_empty_when_file_missing(sheet: Path) -> None:
    assert read_provenance(sheet) == []


def test_append_creates_file_and_round_trips(sheet: Path) -> None:
    append_provenance(sheet, _entry())
    entries = read_provenance(sheet)
    assert len(entries) == 1
    assert entries[0]["record_id"] == "cust_001"
    assert provenance_path(sheet).is_file()


def test_append_validates_required_fields(sheet: Path) -> None:
    with pytest.raises(ProvenanceError, match="record_id"):
        append_provenance(sheet, _entry(record_id=None))
    with pytest.raises(ProvenanceError, match="actor"):
        append_provenance(sheet, _entry(actor=""))


def test_append_appends_subsequent_entries(sheet: Path) -> None:
    append_provenance(sheet, _entry(at="2026-05-09T10:00:00Z"))
    append_provenance(sheet, _entry(at="2026-05-09T10:05:00Z"))
    entries = read_provenance(sheet)
    assert [entry["at"] for entry in entries] == [
        "2026-05-09T10:00:00Z",
        "2026-05-09T10:05:00Z",
    ]


def test_read_rejects_malformed_line(sheet: Path) -> None:
    provenance_path(sheet).write_text(
        json.dumps(_entry()) + "\nnot-json\n",
        encoding="utf-8",
    )
    with pytest.raises(ProvenanceError, match="invalid JSON"):
        read_provenance(sheet)


def test_read_rejects_non_object_line(sheet: Path) -> None:
    provenance_path(sheet).write_text("[1,2,3]\n", encoding="utf-8")
    with pytest.raises(ProvenanceError, match="JSON object"):
        read_provenance(sheet)


# --- latest + history ------------------------------------------------------


def test_latest_returns_most_recent_entry(sheet: Path) -> None:
    append_provenance(sheet, _entry(at="2026-05-09T10:00:00Z"))
    append_provenance(
        sheet,
        _entry(
            at="2026-05-09T11:00:00Z",
            source="human_override",
            actor="human:alice",
            input_hash=None,
        ),
    )

    latest = latest_provenance(sheet, "cust_001", "industry_tag")
    assert latest is not None
    assert latest["source"] == "human_override"
    assert latest["actor"] == "human:alice"


def test_latest_returns_none_when_field_unseen(sheet: Path) -> None:
    append_provenance(sheet, _entry())
    assert latest_provenance(sheet, "cust_002", "industry_tag") is None
    assert latest_provenance(sheet, "cust_001", "summary") is None


def test_field_history_returns_all_entries_in_order(sheet: Path) -> None:
    append_provenance(sheet, _entry(at="2026-05-09T10:00:00Z", source="ai"))
    append_provenance(
        sheet,
        _entry(
            at="2026-05-09T11:00:00Z",
            source="human_override",
            actor="human:alice",
        ),
    )
    append_provenance(
        sheet,
        _entry(
            record_id="cust_002",
            at="2026-05-09T12:00:00Z",
        ),
    )

    history = field_history(sheet, "cust_001", "industry_tag")
    assert [entry["at"] for entry in history] == [
        "2026-05-09T10:00:00Z",
        "2026-05-09T11:00:00Z",
    ]


# --- is_stale --------------------------------------------------------------


def test_is_stale_when_no_entry() -> None:
    assert is_stale(None, "sha256:" + ("a" * 64)) is True


def test_is_stale_when_input_hash_differs() -> None:
    assert (
        is_stale(_entry(input_hash="sha256:" + ("a" * 64)), "sha256:" + ("b" * 64))
        is True
    )


def test_not_stale_when_input_hash_matches() -> None:
    assert (
        is_stale(_entry(input_hash="sha256:" + ("a" * 64)), "sha256:" + ("a" * 64))
        is False
    )
