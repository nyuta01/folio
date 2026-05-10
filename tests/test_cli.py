"""Tests for ``folio.cli`` (Phase 0 CLI MVP)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from folio.cli import app


@pytest.fixture
def runner() -> CliRunner:
    # Click 8.2+ keeps stdout and stderr separate by default.
    return CliRunner()


# --- validate --------------------------------------------------------------


def test_validate_succeeds_on_minimal_sheet(
    runner: CliRunner, minimal_sheet: Path
) -> None:
    result = runner.invoke(app, ["validate", str(minimal_sheet)])
    assert result.exit_code == 0, result.stderr
    assert "contract.yaml is valid" in result.stdout
    assert "0 records" in result.stdout


def test_validate_reports_record_count(
    runner: CliRunner, populated_sheet: Path
) -> None:
    result = runner.invoke(app, ["validate", str(populated_sheet)])
    assert result.exit_code == 0
    assert "3 records" in result.stdout


def test_validate_fails_on_missing_directory(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", str(tmp_path / "missing")])
    assert result.exit_code != 0


# --- query -----------------------------------------------------------------


def test_query_returns_json_rows(runner: CliRunner, populated_sheet: Path) -> None:
    result = runner.invoke(
        app,
        ["query", str(populated_sheet), "SELECT id FROM records ORDER BY id"],
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == [
        {"id": "a"},
        {"id": "b"},
        {"id": "c"},
    ]


def test_query_with_param(runner: CliRunner, populated_sheet: Path) -> None:
    result = runner.invoke(
        app,
        [
            "query",
            str(populated_sheet),
            "SELECT id FROM records WHERE count >= ? ORDER BY id",
            "--param",
            "2",
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == [{"id": "b"}, {"id": "c"}]


def test_query_rejects_writes(runner: CliRunner, populated_sheet: Path) -> None:
    result = runner.invoke(
        app,
        ["query", str(populated_sheet), "INSERT INTO records VALUES ('z','Z',9)"],
    )
    assert result.exit_code == 1
    assert "error:" in result.stderr
    assert "SELECT" in result.stderr


# --- list ------------------------------------------------------------------


def test_list_default_limit(runner: CliRunner, populated_sheet: Path) -> None:
    result = runner.invoke(app, ["list", str(populated_sheet)])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["format"] == "json"
    assert payload["limit"] == 50
    assert len(payload["records"]) == 3
    assert payload["next_cursor"] is None


def test_list_with_filter_and_fields(
    runner: CliRunner, populated_sheet: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "list",
            str(populated_sheet),
            "--filter",
            "count >= ?",
            "--param",
            "2",
            "--fields",
            "id",
        ],
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    ids = sorted(row["id"] for row in payload["records"])
    assert ids == ["b", "c"]
    # Field projection only returns the requested column.
    for row in payload["records"]:
        assert set(row.keys()) == {"id"}


def test_list_pagination(runner: CliRunner, populated_sheet: Path) -> None:
    result = runner.invoke(app, ["list", str(populated_sheet), "--limit", "2"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["next_cursor"] == "2"

    result = runner.invoke(
        app,
        ["list", str(populated_sheet), "--limit", "2", "--cursor", "2"],
    )
    payload = json.loads(result.stdout)
    assert payload["next_cursor"] is None
    assert len(payload["records"]) == 1


# --- count -----------------------------------------------------------------


def test_count_returns_integer_line(
    runner: CliRunner, populated_sheet: Path
) -> None:
    result = runner.invoke(app, ["count", str(populated_sheet)])
    assert result.exit_code == 0, result.stderr
    assert result.stdout.strip() == "3"


def test_count_with_filter(runner: CliRunner, populated_sheet: Path) -> None:
    result = runner.invoke(
        app,
        ["count", str(populated_sheet), "--filter", "count > 1"],
    )
    assert result.exit_code == 0, result.stderr
    assert result.stdout.strip() == "2"


# --- upsert ----------------------------------------------------------------


def test_upsert_from_stdin(runner: CliRunner, minimal_sheet: Path) -> None:
    payload = (
        '{"id": "x", "title": "X", "count": 1}\n'
        '{"id": "y", "title": "Y", "count": 2}\n'
    )
    result = runner.invoke(
        app,
        [
            "upsert",
            str(minimal_sheet),
            "--file",
            "-",
            "--actor",
            "human:smoke",
        ],
        input=payload,
    )
    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body == {"inserted": 2, "updated": 0, "total": 2}


def test_upsert_from_file(
    runner: CliRunner, minimal_sheet: Path, tmp_path: Path
) -> None:
    src = tmp_path / "rows.jsonl"
    src.write_text(
        '{"id": "x", "title": "X", "count": 1}\n', encoding="utf-8"
    )
    result = runner.invoke(
        app,
        [
            "upsert",
            str(minimal_sheet),
            "--file",
            str(src),
            "--actor",
            "human:smoke",
        ],
    )
    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["inserted"] == 1


def test_upsert_requires_actor(runner: CliRunner, minimal_sheet: Path) -> None:
    result = runner.invoke(
        app,
        ["upsert", str(minimal_sheet), "--file", "-"],
        input='{"id": "x", "title": "X"}\n',
    )
    assert result.exit_code != 0
    # Typer surfaces missing --actor as a usage error on stderr. CI's
    # non-TTY rendering interleaves ANSI codes inside the literal, so
    # strip them before searching for the option name.
    raw = (result.stderr or result.stdout) or ""
    plain = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    assert "--actor" in plain or "actor" in plain.lower()


# --- delete ----------------------------------------------------------------


def test_delete_by_repeated_ids(runner: CliRunner, populated_sheet: Path) -> None:
    result = runner.invoke(
        app,
        [
            "delete",
            str(populated_sheet),
            "--ids",
            "a",
            "--ids",
            "c",
            "--actor",
            "human:smoke",
        ],
    )
    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body == {"deleted": 2, "remaining": 1}


def test_delete_by_comma_list(runner: CliRunner, populated_sheet: Path) -> None:
    result = runner.invoke(
        app,
        [
            "delete",
            str(populated_sheet),
            "--ids",
            "a,b",
            "--actor",
            "human:smoke",
        ],
    )
    assert result.exit_code == 0, result.stderr
    body = json.loads(result.stdout)
    assert body == {"deleted": 2, "remaining": 1}
