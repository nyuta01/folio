"""FastAPI app that serves a single Folio sheet (Phase 5 V0–V3).

Routes mirror §19.4. CSRF: a token is issued on the first GET (set as a
``folio_csrf`` cookie and echoed by ``GET /api/csrf``); mutating verbs
must echo it back via the ``X-CSRF-Token`` header. The threat model
here is browser-side CSRF — the bind is ``127.0.0.1`` only, so no
network attacker can read the token (§19.1). Authentication is out of
scope for Phase 5 (deferred to Phase 7).
"""

from __future__ import annotations

import asyncio
import csv as csv_module
import io
import json
import re
import secrets
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from folio import open_sheet
from folio._ai_kind import AIClient
from folio.exceptions import (
    ContractError,
    FolioError,
    LockTimeoutError,
    OperationError,
    PermissionDeniedError,
    QueryError,
    RecordsError,
    SheetError,
)

from ._events import EventBus, make_event

CSRF_COOKIE_NAME = "folio_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


@dataclass
class ViewerSettings:
    """Construction settings for ``build_app``."""

    sheet_path: Path
    default_actor: str | None = None
    ai_client: AIClient | None = None
    static_dir: Path | None = None
    csrf_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    event_bus: EventBus = field(default_factory=EventBus)


# --- Pydantic request bodies ---------------------------------------------


class UpsertBody(BaseModel):
    records: list[dict[str, Any]]
    actor: str | None = None


class QueryBody(BaseModel):
    sql: str
    params: list[Any] | None = None


class MaterializeBody(BaseModel):
    targets: list[str] | None = None
    record_ids: list[str] | None = None
    force: bool = False
    actor: str | None = None


class AddPropertyBody(BaseModel):
    name: str
    logicalType: str = "string"
    description: str | None = None
    required: bool = False
    editable_by: list[str] | None = None
    actor: str | None = None


class UpdatePropertyBody(BaseModel):
    new_name: str | None = None
    logicalType: str | None = None
    description: str | None = None
    required: bool | None = None
    editable_by: list[str] | None = None
    actor: str | None = None


# --- error mapping --------------------------------------------------------


_STATUS_BY_TYPE: dict[type[FolioError], int] = {
    ContractError: 500,
    SheetError: 404,
    RecordsError: 500,
    QueryError: 400,
    PermissionDeniedError: 403,
    OperationError: 400,
    LockTimeoutError: 409,
}


def _error_response(exc: FolioError) -> JSONResponse:
    status = _STATUS_BY_TYPE.get(type(exc), 500)
    body = {"error": {"type": type(exc).__name__, "message": str(exc)}}
    return JSONResponse(status_code=status, content=body)


# --- helpers --------------------------------------------------------------


def _ensure_csrf_cookie(request: Request, response: Response, token: str) -> str:
    """Set ``folio_csrf`` if missing; return the canonical token value."""
    if request.cookies.get(CSRF_COOKIE_NAME) != token:
        response.set_cookie(
            CSRF_COOKIE_NAME,
            token,
            httponly=False,
            samesite="strict",
            secure=False,
        )
    return token


def _check_csrf(request: Request, token: str) -> None:
    header_value = request.headers.get(CSRF_HEADER_NAME)
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    if header_value != token or cookie_value != token:
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")


def _split_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _parse_int(value: str | None, *, name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"{name} must be an integer"
        ) from exc


def build_app(
    *,
    sheet_path: Path | str,
    default_actor: str | None = None,
    ai_client: AIClient | None = None,
    static_dir: Path | str | None = None,
    event_bus: EventBus | None = None,
) -> FastAPI:
    """Construct a FastAPI app that serves the sheet at ``sheet_path``.

    The app is transport-agnostic. Bind to 127.0.0.1 from the CLI so
    the §19.1 invariant (local-only) holds.
    """
    settings = ViewerSettings(
        sheet_path=Path(sheet_path).resolve(),
        default_actor=default_actor,
        ai_client=ai_client,
        static_dir=Path(static_dir).resolve() if static_dir is not None else None,
        event_bus=event_bus or EventBus(),
    )

    if not settings.sheet_path.is_dir():
        raise SheetError(f"viewer sheet path is not a directory: {settings.sheet_path}")

    app = FastAPI(title="folio-viewer", version="0.1.0")
    app.state.settings = settings

    def _open(actor: str | None = None):
        return open_sheet(settings.sheet_path, actor=actor or settings.default_actor)

    @app.exception_handler(FolioError)
    async def _folio_handler(_request: Request, exc: FolioError):
        return _error_response(exc)

    @app.exception_handler(ValidationError)
    async def _pydantic_handler(_request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=400,
            content={"error": {"type": "ValidationError", "message": exc.errors()}},
        )

    # --- CSRF ------------------------------------------------------------

    @app.get("/api/csrf")
    def csrf(request: Request, response: Response) -> dict[str, str]:
        token = _ensure_csrf_cookie(request, response, settings.csrf_token)
        return {"csrf_token": token}

    # --- contract --------------------------------------------------------

    @app.get("/api/contract")
    def get_contract(request: Request, response: Response) -> dict[str, Any]:
        _ensure_csrf_cookie(request, response, settings.csrf_token)
        sheet = _open()
        return sheet.contract.model_dump(mode="json", by_alias=True)

    @app.post("/api/contract/properties")
    def add_property(body: AddPropertyBody, request: Request) -> dict[str, Any]:
        _check_csrf(request, settings.csrf_token)
        actor = body.actor or settings.default_actor
        if actor is None:
            raise HTTPException(status_code=400, detail="actor is required")
        prop = {
            "name": body.name,
            "logicalType": body.logicalType,
        }
        if body.description is not None:
            prop["description"] = body.description
        if body.required:
            prop["required"] = True
        if body.editable_by:
            prop["x-editable-by"] = list(body.editable_by)
        contract = _open(actor=actor).add_property(prop, actor=actor)
        return contract.model_dump(mode="json", by_alias=True)

    @app.patch("/api/contract/properties/{name}")
    def update_property(
        name: str, body: UpdatePropertyBody, request: Request
    ) -> dict[str, Any]:
        _check_csrf(request, settings.csrf_token)
        actor = body.actor or settings.default_actor
        if actor is None:
            raise HTTPException(status_code=400, detail="actor is required")
        contract = _open(actor=actor).update_property(
            name,
            actor=actor,
            new_name=body.new_name,
            logical_type=body.logicalType,
            description=body.description,
            required=body.required,
            editable_by=body.editable_by,
        )
        return contract.model_dump(mode="json", by_alias=True)

    @app.delete("/api/contract/properties/{name}")
    def delete_property(name: str, request: Request) -> dict[str, Any]:
        _check_csrf(request, settings.csrf_token)
        actor = request.headers.get("X-Folio-Actor") or settings.default_actor
        if actor is None:
            raise HTTPException(status_code=400, detail="actor is required")
        contract = _open(actor=actor).delete_property(name, actor=actor)
        return contract.model_dump(mode="json", by_alias=True)

    # --- records ---------------------------------------------------------

    @app.get("/api/records")
    def list_records(
        request: Request,
        response: Response,
        fields: str | None = None,
        limit: str | None = None,
        cursor: str | None = None,
        filter: str | None = None,  # noqa: A002 — keeps spec naming
    ) -> dict[str, Any]:
        _ensure_csrf_cookie(request, response, settings.csrf_token)
        sheet = _open()
        parsed_limit = _parse_int(limit, name="limit") or 50
        return sheet.list_records(
            filter=filter,
            fields=_split_csv(fields),
            limit=parsed_limit,
            cursor=cursor,
            format="json",
        )

    @app.get("/api/records/{record_id}")
    def get_record(
        record_id: str,
        request: Request,
        response: Response,
        fields: str | None = None,
    ) -> dict[str, Any]:
        _ensure_csrf_cookie(request, response, settings.csrf_token)
        sheet = _open()
        record = sheet.get_record(record_id, fields=_split_csv(fields))
        if record is None:
            raise HTTPException(status_code=404, detail=f"record not found: {record_id}")
        return record

    @app.post("/api/records")
    def upsert_records(body: UpsertBody, request: Request) -> dict[str, Any]:
        _check_csrf(request, settings.csrf_token)
        actor = body.actor or settings.default_actor
        if actor is None:
            raise HTTPException(status_code=400, detail="actor is required")
        return _open(actor=actor).upsert_records(body.records)

    @app.delete("/api/records")
    def delete_records(
        request: Request,
        ids: str | None = None,
    ) -> dict[str, Any]:
        _check_csrf(request, settings.csrf_token)
        id_list = _split_csv(ids) or []
        if not id_list:
            raise HTTPException(status_code=400, detail="ids query parameter is required")
        actor = request.headers.get("X-Folio-Actor") or settings.default_actor
        if actor is None:
            raise HTTPException(status_code=400, detail="actor is required")
        return _open(actor=actor).delete_records(id_list)

    # --- query -----------------------------------------------------------

    @app.post("/api/query")
    def query(body: QueryBody, request: Request, response: Response) -> dict[str, Any]:
        _ensure_csrf_cookie(request, response, settings.csrf_token)
        rows = _open().query(body.sql, body.params)
        return {"rows": rows, "count": len(rows)}

    # --- materialize -----------------------------------------------------

    @app.get("/api/status")
    def status(
        request: Request,
        response: Response,
        targets: str | None = None,
    ) -> dict[str, Any]:
        _ensure_csrf_cookie(request, response, settings.csrf_token)
        return _open().materialization_status(targets=_split_csv(targets))

    @app.post("/api/materialize")
    def materialize(body: MaterializeBody, request: Request) -> dict[str, Any]:
        _check_csrf(request, settings.csrf_token)
        actor = body.actor or settings.default_actor
        if actor is None:
            raise HTTPException(status_code=400, detail="actor is required")
        bus = settings.event_bus
        bus.publish(
            make_event(
                "materialize.start",
                actor=actor,
                targets=body.targets,
                record_ids=body.record_ids,
                force=body.force,
            )
        )
        try:
            envelope = _open(actor=actor).materialize(
                targets=body.targets,
                record_ids=body.record_ids,
                force=body.force,
                ai_client=settings.ai_client,
            )
        except FolioError as exc:
            bus.publish(
                make_event(
                    "materialize.error",
                    actor=actor,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            raise
        bus.publish(
            make_event(
                "materialize.end",
                actor=actor,
                materialized=envelope.get("materialized"),
                skipped=envelope.get("skipped"),
                failures=len(envelope.get("failures") or []),
                total_cost=envelope.get("total_cost"),
            )
        )
        return envelope

    # --- provenance ------------------------------------------------------

    @app.get("/api/provenance")
    def provenance(
        request: Request,
        response: Response,
        record_id: str,
        field: str,
        history: bool = False,
    ) -> Any:
        _ensure_csrf_cookie(request, response, settings.csrf_token)
        return _open().provenance(record_id=record_id, field=field, history=history)

    # --- SSE event stream ------------------------------------------------

    async def _event_stream(request: Request) -> AsyncIterator[bytes]:
        queue = settings.event_bus.subscribe()
        try:
            yield b": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield b": keepalive\n\n"
                    continue
                payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
                yield b"event: " + event["kind"].encode("utf-8") + b"\n"
                yield b"data: " + payload + b"\n\n"
        finally:
            settings.event_bus.unsubscribe(queue)

    @app.get("/events")
    async def events(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _event_stream(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # --- export -----------------------------------------------------------

    @app.get("/api/export/{fmt}")
    def export_sheet(fmt: str) -> Response:
        """Download the sheet's data (json/csv/xlsx) or the whole sheet
        directory (zip). Implemented in pure stdlib so packaged installs
        don't need an extra dependency just to emit a spreadsheet."""
        fmt_lower = fmt.lower()
        sheet = _open()
        base = _safe_filename(sheet.contract.id or settings.sheet_path.name)

        if fmt_lower == "json":
            records = _read_all_records(settings.sheet_path)
            body = json.dumps(records, ensure_ascii=False, indent=2)
            return _download_response(
                body.encode("utf-8"),
                f"{base}.json",
                "application/json; charset=utf-8",
            )
        if fmt_lower in {"csv", "tsv"}:
            records = _read_all_records(settings.sheet_path)
            columns = [p.name for p in sheet.contract.main_schema.properties]
            body = _records_to_csv(
                records, columns, sep="\t" if fmt_lower == "tsv" else ","
            )
            # UTF-8 BOM so Excel auto-detects encoding for non-ASCII data.
            return _download_response(
                b"\xef\xbb\xbf" + body.encode("utf-8"),
                f"{base}.{fmt_lower}",
                f"text/{fmt_lower}; charset=utf-8",
            )
        if fmt_lower == "xlsx":
            records = _read_all_records(settings.sheet_path)
            columns = [p.name for p in sheet.contract.main_schema.properties]
            body = _records_to_xlsx(records, columns, sheet_name="records")
            return _download_response(
                body,
                f"{base}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        if fmt_lower == "zip":
            body = _sheet_dir_to_zip(settings.sheet_path)
            return _download_response(
                body,
                f"{base}.zip",
                "application/zip",
            )
        raise HTTPException(
            status_code=400,
            detail=f"unsupported export format: {fmt!r} (expected json, csv, xlsx, or zip)",
        )

    # --- static frontend -------------------------------------------------

    if settings.static_dir is not None and settings.static_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=settings.static_dir, html=True),
            name="frontend",
        )

    return app


# --- export helpers ------------------------------------------------------


_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(stem: str) -> str:
    """Reduce a sheet id to a safe ASCII filename stem."""
    cleaned = _SAFE_RE.sub("-", stem).strip("-")
    return cleaned or "sheet"


def _download_response(body: bytes, filename: str, media_type: str) -> Response:
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _read_all_records(sheet_path: Path) -> list[dict[str, Any]]:
    """Read records.jsonl directly so we bypass the SDK's paginated
    list_records (default limit 50) and reliably get every row."""
    records_path = sheet_path / "records.jsonl"
    if not records_path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with records_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _records_to_csv(
    records: list[dict[str, Any]], columns: list[str], sep: str = ","
) -> str:
    """Render records as CSV/TSV. Complex values (lists, dicts) are
    JSON-stringified so the file round-trips through Excel without
    Python's `repr` quoting them awkwardly."""
    out = io.StringIO()
    writer = csv_module.writer(out, delimiter=sep, lineterminator="\n")
    writer.writerow(columns)
    for rec in records:
        row = []
        for col in columns:
            v = rec.get(col)
            if v is None:
                row.append("")
            elif isinstance(v, bool):
                row.append("TRUE" if v else "FALSE")
            elif isinstance(v, (dict, list)):
                row.append(json.dumps(v, ensure_ascii=False))
            else:
                row.append(str(v))
        writer.writerow(row)
    return out.getvalue()


def _xlsx_col_letter(n: int) -> str:
    """0-indexed column → A, B, …, Z, AA, AB, …"""
    s = ""
    while True:
        s = chr(ord("A") + n % 26) + s
        n = n // 26 - 1
        if n < 0:
            return s


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _records_to_xlsx(
    records: list[dict[str, Any]],
    columns: list[str],
    sheet_name: str = "records",
) -> bytes:
    """Render records as a minimal .xlsx workbook using stdlib zipfile
    + handwritten OOXML. Avoids pulling in openpyxl just to emit one
    flat sheet. Limits us to inline strings / numbers / booleans, which
    is exactly what Folio records carry — complex types JSON-stringify."""
    safe_sheet_name = (sheet_name or "records").replace(":", "_").replace("/", "_")[:31]
    rows_xml: list[str] = []
    # Header row
    header_cells = "".join(
        f'<c r="{_xlsx_col_letter(i)}1" t="inlineStr"><is><t xml:space="preserve">{_xml_escape(name)}</t></is></c>'
        for i, name in enumerate(columns)
    )
    rows_xml.append(f'<row r="1">{header_cells}</row>')
    # Data rows
    for ridx, rec in enumerate(records, start=2):
        cells: list[str] = []
        for cidx, col in enumerate(columns):
            v = rec.get(col)
            ref = f"{_xlsx_col_letter(cidx)}{ridx}"
            if v is None:
                continue
            if isinstance(v, bool):
                cells.append(f'<c r="{ref}" t="b"><v>{1 if v else 0}</v></c>')
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                cells.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                if isinstance(v, (dict, list)):
                    text = json.dumps(v, ensure_ascii=False)
                else:
                    text = str(v)
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_xml_escape(text)}</t></is></c>'
                )
        rows_xml.append(f'<row r="{ridx}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rows_xml)}</sheetData>'
        "</worksheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{_xml_escape(safe_sheet_name)}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def _zip_skip_path(rel: Path) -> bool:
    """Decide whether a file should be excluded from the sheet zip.
    Drops the usual VCS / cache / lock noise so the archive is just
    the sheet content a recipient would want."""
    parts = rel.parts
    if any(p.startswith(".") for p in parts):
        return True
    if "__pycache__" in parts:
        return True
    if "node_modules" in parts:
        return True
    if rel.suffix == ".lock":
        return True
    if rel.suffix == ".pyc":
        return True
    return False


def _sheet_dir_to_zip(sheet_path: Path) -> bytes:
    """Bundle the entire sheet directory into a zip archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        root_name = sheet_path.name or "sheet"
        files: Iterable[Path] = sorted(sheet_path.rglob("*"))
        for path in files:
            if not path.is_file():
                continue
            rel = path.relative_to(sheet_path)
            if _zip_skip_path(rel):
                continue
            zf.write(path, arcname=f"{root_name}/{rel.as_posix()}")
    return buf.getvalue()


__all__ = [
    "CSRF_COOKIE_NAME",
    "CSRF_HEADER_NAME",
    "EventBus",
    "ViewerSettings",
    "build_app",
    "make_event",
]
