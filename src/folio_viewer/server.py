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
import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

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

    # --- static frontend -------------------------------------------------

    if settings.static_dir is not None and settings.static_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=settings.static_dir, html=True),
            name="frontend",
        )

    return app


__all__ = [
    "CSRF_COOKIE_NAME",
    "CSRF_HEADER_NAME",
    "EventBus",
    "ViewerSettings",
    "build_app",
    "make_event",
]
