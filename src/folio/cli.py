"""Folio command-line interface.

A thin Typer wrapper over the Phase 0 SDK. The six verbs map one-to-one to
``Sheet`` operations defined in §17 of the design overview.
"""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import typer

from . import open_sheet
from .exceptions import FolioError

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Folio: portable, AI-native data sheets.",
)

SHEET_ARGUMENT = typer.Argument(
    ...,
    exists=True,
    file_okay=False,
    dir_okay=True,
    readable=True,
    resolve_path=True,
    help="Path to a Folio sheet directory.",
)


def _handle_folio_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except FolioError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=1)

    return wrapper


def _emit_json(value: Any) -> None:
    typer.echo(json.dumps(value, ensure_ascii=False))


def _read_records_from_source(file: str) -> list[dict[str, Any]]:
    if file == "-":
        text = sys.stdin.read()
    else:
        text = Path(file).read_text(encoding="utf-8")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FolioError(
                f"input line {line_number}: invalid JSON ({exc.msg})"
            ) from exc
        if not isinstance(value, dict):
            raise FolioError(
                f"input line {line_number}: each record must be a JSON object"
            )
        records.append(value)
    return records


def _split_id_list(values: Sequence[str]) -> list[str]:
    flat: list[str] = []
    for raw in values:
        for part in raw.split(","):
            piece = part.strip()
            if piece:
                flat.append(piece)
    return flat


# --- commands --------------------------------------------------------------


@app.command(help="Validate contract.yaml and confirm records.jsonl is readable.")
@_handle_folio_errors
def validate(
    sheet: Path = SHEET_ARGUMENT,
) -> None:
    s = open_sheet(sheet)
    contract = s.get_contract()
    typer.echo(
        f"contract.yaml is valid: {contract.id} v{contract.version} "
        f"({len(contract.main_schema.properties)} fields)"
    )
    rows = s.query("SELECT COUNT(*) AS n FROM records")
    count = int(rows[0]["n"])
    plural = "s" if count != 1 else ""
    typer.echo(f"records.jsonl is readable ({count} record{plural})")


@app.command(name="query", help="Execute DuckDB SQL against the sheet's records view.")
@_handle_folio_errors
def query_command(
    sheet: Path = SHEET_ARGUMENT,
    sql: str = typer.Argument(..., help="A SELECT-style DuckDB query."),
    params: Optional[list[str]] = typer.Option(
        None,
        "--param",
        help="Positional ? parameter (repeat for multiple).",
    ),
) -> None:
    s = open_sheet(sheet)
    rows = s.query(sql, params or None)
    _emit_json(rows)


@app.command(name="list", help="List records as a JSON envelope.")
@_handle_folio_errors
def list_command(
    sheet: Path = SHEET_ARGUMENT,
    filter_: Optional[str] = typer.Option(
        None,
        "--filter",
        help="DuckDB WHERE-clause string. Use '?' for parameter placeholders.",
    ),
    fields: Optional[list[str]] = typer.Option(
        None,
        "--fields",
        help="Project a subset of fields (repeat for multiple).",
    ),
    limit: int = typer.Option(50, "--limit", min=1, help="Maximum rows to return."),
    cursor: Optional[str] = typer.Option(
        None,
        "--cursor",
        help="Pagination cursor returned by a previous list call.",
    ),
    params: Optional[list[str]] = typer.Option(
        None,
        "--param",
        help="Positional ? parameter for --filter (repeat for multiple).",
    ),
) -> None:
    s = open_sheet(sheet)
    result = s.list_records(
        filter=filter_,
        fields=fields,
        limit=limit,
        cursor=cursor,
        params=params or None,
    )
    _emit_json(result)


@app.command(help="Count records, optionally with a WHERE-clause filter.")
@_handle_folio_errors
def count(
    sheet: Path = SHEET_ARGUMENT,
    filter_: Optional[str] = typer.Option(
        None,
        "--filter",
        help="DuckDB WHERE-clause string. Use '?' for parameter placeholders.",
    ),
    params: Optional[list[str]] = typer.Option(
        None,
        "--param",
        help="Positional ? parameter for --filter (repeat for multiple).",
    ),
) -> None:
    s = open_sheet(sheet)
    sql = "SELECT COUNT(*) AS n FROM records"
    if filter_:
        sql += f" WHERE {filter_}"
    rows = s.query(sql, params or None)
    typer.echo(int(rows[0]["n"]))


@app.command(help="Insert or update records by primaryKey.")
@_handle_folio_errors
def upsert(
    sheet: Path = SHEET_ARGUMENT,
    file: str = typer.Option(
        "-",
        "--file",
        help="Path to a JSONL file with one record per line, or '-' for stdin.",
    ),
    actor: str = typer.Option(..., "--actor", help="Actor performing the upsert."),
) -> None:
    records = _read_records_from_source(file)
    s = open_sheet(sheet, actor=actor)
    result = s.upsert_records(records)
    _emit_json(result)


@app.command(help="Delete records by primaryKey id.")
@_handle_folio_errors
def delete(
    sheet: Path = SHEET_ARGUMENT,
    ids: list[str] = typer.Option(
        ...,
        "--ids",
        help="Record IDs (comma-separated or repeat --ids).",
    ),
    actor: str = typer.Option(..., "--actor", help="Actor performing the delete."),
) -> None:
    flat_ids = _split_id_list(ids)
    if not flat_ids:
        raise FolioError("--ids must include at least one record id")
    s = open_sheet(sheet, actor=actor)
    result = s.delete_records(flat_ids)
    _emit_json(result)


def main() -> None:
    """Entry point registered as the ``folio`` console script."""
    app()


if __name__ == "__main__":
    main()
