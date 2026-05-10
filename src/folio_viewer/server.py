"""FastAPI app that serves a single Folio sheet (Phase 5 V0–V3).

Routes mirror §19.4. CSRF: a token is issued on the first GET (set as a
``folio_csrf`` cookie and echoed by ``GET /api/csrf``); mutating verbs
must echo it back via the ``X-CSRF-Token`` header. The threat model
here is browser-side CSRF — the bind is ``127.0.0.1`` only, so no
network attacker can read the token (§19.1). Authentication is out of
scope for Phase 5 (deferred to Phase 7).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
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
        return _open(actor=actor).materialize(
            targets=body.targets,
            record_ids=body.record_ids,
            force=body.force,
            ai_client=settings.ai_client,
        )

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

    # --- static frontend -------------------------------------------------

    if settings.static_dir is not None and settings.static_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=settings.static_dir, html=True),
            name="frontend",
        )

    return app


__all__ = ["CSRF_COOKIE_NAME", "CSRF_HEADER_NAME", "ViewerSettings", "build_app"]
