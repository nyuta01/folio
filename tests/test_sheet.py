"""Tests for ``folio.sheet`` (Phase 0 core operations)."""

from __future__ import annotations

import json
import os
import textwrap
import threading
from pathlib import Path

import pytest

import folio
from folio import (
    OperationError,
    PermissionDeniedError,
    QueryError,
    SheetError,
    open_sheet,
)


# --- get_contract ----------------------------------------------------------


def test_get_contract(minimal_sheet: Path) -> None:
    sheet = open_sheet(minimal_sheet)
    assert sheet.get_contract().id == "test"
    assert sheet.contract.main_schema.name == "items"


def test_open_sheet_rejects_non_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-dir"
    file_path.write_text("", encoding="utf-8")
    with pytest.raises(SheetError, match="not a directory"):
        open_sheet(file_path)


# --- query -----------------------------------------------------------------


def test_query_empty_sheet(minimal_sheet: Path) -> None:
    sheet = open_sheet(minimal_sheet)
    rows = sheet.query("SELECT COUNT(*) AS n FROM records")
    assert rows == [{"n": 0}]


def test_query_populated_sheet(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    rows = sheet.query("SELECT id, title FROM records ORDER BY id")
    assert rows == [
        {"id": "a", "title": "Alpha"},
        {"id": "b", "title": "Beta"},
        {"id": "c", "title": "Gamma"},
    ]


def test_query_with_parameters(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    rows = sheet.query(
        "SELECT id FROM records WHERE count >= ? ORDER BY id",
        [2],
    )
    assert rows == [{"id": "b"}, {"id": "c"}]


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO records VALUES ('z', 'Z', 99)",
        "UPDATE records SET count = 0",
        "DELETE FROM records",
        "CREATE TABLE foo (x INT)",
        "DROP VIEW records",
        "ALTER TABLE records ADD COLUMN x INT",
        "COPY records TO 'out.csv'",
    ],
)
def test_query_rejects_writes(populated_sheet: Path, sql: str) -> None:
    sheet = open_sheet(populated_sheet)
    with pytest.raises(QueryError):
        sheet.query(sql)


def test_query_strips_comments_before_keyword_check(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    rows = sheet.query(
        "-- list everything\nSELECT id FROM records ORDER BY id LIMIT 1"
    )
    assert rows == [{"id": "a"}]


# --- list_records ----------------------------------------------------------


def test_list_records_empty(minimal_sheet: Path) -> None:
    sheet = open_sheet(minimal_sheet)
    result = sheet.list_records()
    assert result["records"] == []
    assert result["format"] == "json"
    assert result["limit"] == 50
    assert result["next_cursor"] is None


def test_list_records_with_filter_and_fields(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    result = sheet.list_records(
        filter="count > ?",
        params=[1],
        fields=["id", "count"],
    )
    rows = sorted(result["records"], key=lambda row: row["id"])
    assert rows == [
        {"id": "b", "count": 2},
        {"id": "c", "count": 3},
    ]


def test_list_records_pagination(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    page1 = sheet.list_records(limit=2)
    assert len(page1["records"]) == 2
    assert page1["next_cursor"] == "2"

    page2 = sheet.list_records(limit=2, cursor=page1["next_cursor"])
    assert len(page2["records"]) == 1
    assert page2["next_cursor"] is None


def test_list_records_rejects_unknown_field(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    with pytest.raises(OperationError, match="unknown field"):
        sheet.list_records(fields=["does_not_exist"])


# --- get_record ------------------------------------------------------------


def test_get_record_found(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    row = sheet.get_record("b")
    assert row is not None
    assert row["title"] == "Beta"
    assert row["count"] == 2


def test_get_record_missing_returns_none(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    assert sheet.get_record("zzz") is None


def test_get_record_with_field_projection(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    row = sheet.get_record("a", fields=["id", "title"])
    assert row == {"id": "a", "title": "Alpha"}


# --- upsert_records --------------------------------------------------------


def test_upsert_inserts_new_record(minimal_sheet: Path) -> None:
    sheet = open_sheet(minimal_sheet, actor="agent:test")
    result = sheet.upsert_records(
        [{"id": "x", "title": "X", "count": 7}]
    )
    assert result == {"inserted": 1, "updated": 0, "total": 1}
    assert sheet.get_record("x") == {"id": "x", "title": "X", "count": 7}


def test_upsert_updates_existing_by_primary_key(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet, actor="agent:test")
    result = sheet.upsert_records([{"id": "b", "count": 99}])
    assert result == {"inserted": 0, "updated": 1, "total": 3}

    row = sheet.get_record("b")
    assert row["count"] == 99
    assert row["title"] == "Beta"  # untouched fields are preserved


def test_upsert_requires_actor(minimal_sheet: Path) -> None:
    sheet = open_sheet(minimal_sheet)
    with pytest.raises(OperationError, match="actor"):
        sheet.upsert_records([{"id": "x", "title": "X"}])


def test_upsert_requires_primary_key(minimal_sheet: Path) -> None:
    sheet = open_sheet(minimal_sheet, actor="agent:test")
    with pytest.raises(OperationError, match="primaryKey"):
        sheet.upsert_records([{"title": "no id"}])


def test_upsert_validates_required_fields_on_insert(minimal_sheet: Path) -> None:
    sheet = open_sheet(minimal_sheet, actor="agent:test")
    with pytest.raises(OperationError, match="required field"):
        sheet.upsert_records([{"id": "x"}])  # missing title


def test_upsert_partial_update_is_allowed_when_required_already_set(
    populated_sheet: Path,
) -> None:
    sheet = open_sheet(populated_sheet, actor="agent:test")
    # Updating only count for an existing record is fine because title is
    # already set on disk and the merged record satisfies required-fields.
    sheet.upsert_records([{"id": "a", "count": 42}])
    assert sheet.get_record("a")["count"] == 42


def test_upsert_actor_argument_overrides_instance(minimal_sheet: Path) -> None:
    sheet = open_sheet(minimal_sheet, actor="agent:default")
    sheet.upsert_records(
        [{"id": "x", "title": "X"}],
        actor="human:alice",
    )
    assert sheet.get_record("x") is not None


# --- editable_by enforcement ----------------------------------------------


@pytest.fixture
def restricted_sheet(tmp_path: Path) -> Path:
    sheet = tmp_path / "restricted"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            """
            apiVersion: v3.0.0
            kind: DataContract
            id: restricted
            name: restricted
            version: 1.0.0
            schema:
              - name: t
                physicalType: jsonl
                properties:
                  - name: id
                    logicalType: string
                    primaryKey: true
                    required: true
                  - name: tag
                    logicalType: string
                    x-editable-by: ["agent:*"]
                  - name: notes
                    logicalType: string
            """
        ).strip(),
        encoding="utf-8",
    )
    (sheet / "records.jsonl").write_text("", encoding="utf-8")
    return sheet


def test_editable_by_allows_matching_actor(restricted_sheet: Path) -> None:
    sheet = open_sheet(restricted_sheet, actor="agent:bot")
    sheet.upsert_records([{"id": "a", "tag": "ok"}])
    assert sheet.get_record("a")["tag"] == "ok"


def test_editable_by_rejects_non_matching_actor(restricted_sheet: Path) -> None:
    sheet = open_sheet(restricted_sheet, actor="human:alice")
    with pytest.raises(PermissionDeniedError, match="cannot edit field 'tag'"):
        sheet.upsert_records([{"id": "a", "tag": "no"}])


def test_editable_by_ignores_fields_without_restriction(
    restricted_sheet: Path,
) -> None:
    sheet = open_sheet(restricted_sheet, actor="human:alice")
    # 'notes' has no x-editable-by, so any actor may edit it.
    sheet.upsert_records([{"id": "a", "notes": "free"}])
    assert sheet.get_record("a")["notes"] == "free"


# --- delete_records --------------------------------------------------------


def test_delete_records(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet, actor="human:alice")
    result = sheet.delete_records(["a", "c"])
    assert result == {"deleted": 2, "remaining": 1}
    rows = sheet.query("SELECT id FROM records")
    assert rows == [{"id": "b"}]


def test_delete_records_requires_actor(populated_sheet: Path) -> None:
    sheet = open_sheet(populated_sheet)
    with pytest.raises(OperationError, match="actor"):
        sheet.delete_records(["a"])


# --- atomic write + lock invariants ---------------------------------------


def test_atomic_write_preserves_original_on_failure(
    populated_sheet: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sheet = open_sheet(populated_sheet, actor="agent:test")

    from folio import _records as records_module

    def failing_replace(*args: object, **kwargs: object) -> None:
        raise OSError("simulated failure")

    monkeypatch.setattr(records_module.os, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated"):
        sheet.upsert_records([{"id": "z", "title": "Z", "count": 99}])

    monkeypatch.undo()

    rows = sheet.query("SELECT id FROM records ORDER BY id")
    assert [row["id"] for row in rows] == ["a", "b", "c"]
    leftovers = list(populated_sheet.glob(".records.*.tmp"))
    assert leftovers == []


def test_lock_serializes_concurrent_writers(populated_sheet: Path) -> None:
    sheet_a = open_sheet(populated_sheet, actor="agent:1")
    sheet_b = open_sheet(populated_sheet, actor="agent:2")

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def writer(sheet: folio.Sheet, payload: dict[str, object]) -> None:
        barrier.wait()
        try:
            sheet.upsert_records([payload])
        except BaseException as exc:  # pragma: no cover - propagated below
            errors.append(exc)

    t1 = threading.Thread(
        target=writer, args=(sheet_a, {"id": "row1", "title": "row1", "count": 100})
    )
    t2 = threading.Thread(
        target=writer, args=(sheet_b, {"id": "row2", "title": "row2", "count": 200})
    )
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert errors == []

    rows = sheet_a.query(
        "SELECT id FROM records WHERE id LIKE 'row%' ORDER BY id"
    )
    assert sorted(row["id"] for row in rows) == ["row1", "row2"]


def test_records_jsonl_lines_are_valid_json(populated_sheet: Path) -> None:
    """After upsert, every line of records.jsonl must round-trip as JSON."""
    sheet = open_sheet(populated_sheet, actor="agent:test")
    sheet.upsert_records([{"id": "d", "title": "Delta", "count": 4}])

    body = (populated_sheet / "records.jsonl").read_text(encoding="utf-8")
    for line in body.splitlines():
        assert json.loads(line)
    # Trailing newline preserved
    assert body.endswith("\n")
