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
from .readme import ReadmeError
from .scripts import SCRIPT_LANGUAGE_BY_EXTENSION, discover_scripts
from .sheet import _default_ai_client_factory  # exposed for monkey-patching in tests

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


@app.command(help="Validate contract.yaml, records.jsonl, and README frontmatter.")
@_handle_folio_errors
def validate(
    sheet: Path = SHEET_ARGUMENT,
    strict: bool = typer.Option(
        False,
        "--strict/--lenient",
        help="Treat README frontmatter problems as errors.",
    ),
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

    try:
        metadata = s.metadata
    except ReadmeError as exc:
        if strict:
            raise
        typer.echo(f"warning: README.md frontmatter: {exc}", err=True)
        return

    if metadata is not None:
        typer.echo(
            "README.md frontmatter is valid "
            f"(purpose: {metadata.purpose}, default_actor: {metadata.default_actor})"
        )


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


@app.command(name="list", help="List records as a JSON envelope (records may be json or toon).")
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
    format_: str = typer.Option(
        "json",
        "--format",
        help="Records wire format: json (default) or toon.",
    ),
) -> None:
    s = open_sheet(sheet)
    result = s.list_records(
        filter=filter_,
        fields=fields,
        limit=limit,
        cursor=cursor,
        params=params or None,
        format=format_,
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


@app.command(help="Materialize derived fields. Defaults to every derivation.")
@_handle_folio_errors
def materialize(
    sheet: Path = SHEET_ARGUMENT,
    target: Optional[str] = typer.Argument(
        None,
        help="Single derivation target. Omit to materialize every derivation.",
    ),
    ids: Optional[list[str]] = typer.Option(
        None,
        "--ids",
        help="Limit to specific record IDs (comma-separated or repeat --ids).",
    ),
    force: bool = typer.Option(
        False,
        "--force/--no-force",
        help="Recompute even when the input_hash matches and human_override is set.",
    ),
    actor: str = typer.Option(..., "--actor", help="Actor performing the materialize."),
) -> None:
    s = open_sheet(sheet, actor=actor)
    target_list = [target] if target else None
    record_ids = _split_id_list(ids) if ids else None
    result = s.materialize(
        targets=target_list,
        record_ids=record_ids or None,
        force=force,
    )
    _emit_json(result)


@app.command(help="Print materialization counts per derived field.")
@_handle_folio_errors
def status(
    sheet: Path = SHEET_ARGUMENT,
    target: Optional[str] = typer.Argument(
        None, help="Single derivation target. Omit for every derivation."
    ),
) -> None:
    s = open_sheet(sheet)
    targets = [target] if target else None
    result = s.materialization_status(targets=targets)
    _emit_json(result)


@app.command(help="Print provenance for a record × field.")
@_handle_folio_errors
def provenance(
    sheet: Path = SHEET_ARGUMENT,
    record_id: str = typer.Argument(..., help="Primary key of the record."),
    field: str = typer.Argument(..., help="Field name."),
    history: bool = typer.Option(
        False,
        "--history/--latest",
        help="Print every entry in the append-only log instead of just the latest.",
    ),
) -> None:
    s = open_sheet(sheet)
    result = s.provenance(record_id=record_id, field=field, history=history)
    if result is None:
        _emit_json(None)
    else:
        _emit_json(result)


script_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Reusable scripts under sheet/scripts/.",
)
app.add_typer(script_app, name="script")


export_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Export sheet metadata in interoperable formats.",
)
app.add_typer(export_app, name="export")


@export_app.command(
    "datapackage",
    help="Emit a Frictionless Data Package descriptor for a sheet.",
)
@_handle_folio_errors
def export_datapackage(
    sheet: Path = SHEET_ARGUMENT,
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        help="Destination JSON file (defaults to <sheet>/datapackage.json).",
    ),
    stdout: bool = typer.Option(
        False,
        "--stdout/--write",
        help="Print the descriptor to stdout instead of writing a file.",
    ),
) -> None:
    from .contract import load_contract
    from .datapackage import build_descriptor, write_datapackage

    if stdout:
        descriptor = build_descriptor(load_contract(sheet))
        typer.echo(
            json.dumps(descriptor, ensure_ascii=False, indent=2, sort_keys=True)
        )
        return

    target = write_datapackage(sheet, out)
    typer.echo(f"wrote {target}")


@script_app.command("list", help="List runnable scripts under sheet/scripts/.")
@_handle_folio_errors
def script_list(
    sheet: Path = SHEET_ARGUMENT,
) -> None:
    discovered = discover_scripts(sheet)
    payload = [
        {
            "name": name,
            "language": SCRIPT_LANGUAGE_BY_EXTENSION[path.suffix],
            "path": str(path.relative_to(sheet)),
        }
        for name, path in discovered.items()
    ]
    _emit_json(payload)


@script_app.command("run", help="Run a script by basename.")
@_handle_folio_errors
def script_run(
    sheet: Path = SHEET_ARGUMENT,
    name: str = typer.Argument(..., help="Script basename (no extension)."),
    args: Optional[list[str]] = typer.Argument(
        None, help="Arguments forwarded to the script after the sheet path."
    ),
    timeout: float = typer.Option(
        60.0,
        "--timeout",
        min=0.1,
        help="Maximum execution time in seconds.",
    ),
) -> None:
    s = open_sheet(sheet)
    result = s.run_script(name=name, args=args or [], timeout_seconds=timeout)
    _emit_json(
        {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": result.duration_seconds,
        }
    )


skill_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Packaged how-to procedures under sheet/skills/.",
)
app.add_typer(skill_app, name="skill")


@skill_app.command("list", help="List skills declared under sheet/skills/.")
@_handle_folio_errors
def skill_list(
    sheet: Path = SHEET_ARGUMENT,
) -> None:
    s = open_sheet(sheet)
    payload = [
        {
            "name": skill.name,
            "description": skill.description,
            "audience": skill.audience,
            "arguments": [a.model_dump(exclude_none=True) for a in skill.arguments],
            "tools": skill.tools,
            "allowed_actors": skill.allowed_actors,
        }
        for skill in s.list_skills()
    ]
    _emit_json(payload)


@skill_app.command(
    "show",
    help="Show the rendered body of a skill, optionally with arguments filled.",
)
@_handle_folio_errors
def skill_show(
    sheet: Path = SHEET_ARGUMENT,
    name: str = typer.Argument(..., help="Skill name (basename of skills/<name>.md)."),
    arg: Optional[list[str]] = typer.Option(
        None,
        "--arg",
        help="Argument substitution in the form name=value. Repeatable.",
    ),
) -> None:
    s = open_sheet(sheet)
    args: dict[str, str] = {}
    for item in arg or []:
        if "=" not in item:
            raise typer.BadParameter(f"--arg must be in name=value form, got {item!r}")
        k, _, v = item.partition("=")
        args[k] = v
    typer.echo(s.render_skill(name, args))


@skill_app.command("validate", help="Validate every skills/*.md under a sheet.")
@_handle_folio_errors
def skill_validate(
    sheet: Path = SHEET_ARGUMENT,
) -> None:
    s = open_sheet(sheet)
    skills = s.list_skills()
    typer.echo(f"{len(skills)} skill(s) validated under {sheet}/skills/")
    if not skills:
        return
    width = max(len(skill.name) for skill in skills)
    for skill in skills:
        typer.echo(f"  ok  {skill.name:<{width}}  {skill.description}")


@app.command(
    name="serve",
    help="Serve <sheet> via folio-viewer (alias for `folio-viewer serve`).",
)
def serve(
    sheet: Path = SHEET_ARGUMENT,
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Bind address (defaults to 127.0.0.1; do not change without a reason).",
    ),
    port: int = typer.Option(
        3000,
        "--port",
        min=1,
        max=65535,
        help="TCP port to bind.",
    ),
    actor: Optional[str] = typer.Option(
        None,
        "--actor",
        help="Default actor for write routes when callers do not pass one.",
    ),
    static_dir: Optional[Path] = typer.Option(
        None,
        "--static-dir",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Optional pre-built frontend directory (defaults to <repo>/viewer/dist if present).",
    ),
) -> None:
    # Lazy-import so `folio` does not pay the fastapi/uvicorn import cost
    # for unrelated verbs, and so drift-check's viewer-only invariant
    # holds at static analysis time.
    from folio_viewer.cli import serve as viewer_serve  # noqa: PLC0415

    viewer_serve(
        sheet=sheet,
        host=host,
        port=port,
        actor=actor,
        static_dir=static_dir,
    )


def main() -> None:
    """Entry point registered as the ``folio`` console script."""
    app()


if __name__ == "__main__":
    main()
