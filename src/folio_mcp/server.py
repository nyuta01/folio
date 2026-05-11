"""FastMCP server that exposes the nine Folio SDK operations as tools.

Each tool resolves ``sheet_path`` against the configured root and rejects
paths that escape the root. The materialize tool routes through
``Sheet.materialize`` so it inherits future Phase 4 extension kinds
without further changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Literal

from fastmcp import FastMCP

from folio import open_sheet
from folio._ai_kind import AIClient
from folio._skill import Skill, load_skills
from folio.exceptions import FolioError, SheetError, SkillError


def build_server(
    *,
    root: str | Path,
    default_actor: str | None = None,
    ai_client: AIClient | None = None,
    name: str = "folio",
) -> FastMCP:
    """Construct a configured ``FastMCP`` server.

    Args:
        root: Directory that holds one or more sheets. Tool calls'
            ``sheet_path`` is resolved against it; paths that escape
            the root are rejected.
        default_actor: Fallback actor when a write tool is invoked
            without an explicit ``actor`` argument. ``None`` means
            writes always require ``actor``.
        ai_client: Optional :class:`folio._ai_kind.AIClient` used by the
            ``materialize`` tool. Tests inject ``StubAIClient``;
            production callers leave this ``None`` and the SDK
            constructs the default Anthropic adapter.
        name: MCP server name (defaults to ``"folio"``).
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise SheetError(f"MCP root must be a directory: {root_path}")

    def _resolve(sheet_path: str) -> Path:
        target = (root_path / sheet_path).resolve()
        try:
            target.relative_to(root_path)
        except ValueError as exc:
            raise FolioError(
                f"sheet_path must live under the MCP root: {sheet_path}"
            ) from exc
        if not target.is_dir():
            raise SheetError(f"sheet not found under root: {sheet_path}")
        return target

    def _open(sheet_path: str, actor: str | None = None):
        return open_sheet(_resolve(sheet_path), actor=actor or default_actor)

    mcp = FastMCP(name=name)

    @mcp.tool
    def get_contract(sheet_path: str) -> dict[str, Any]:
        """Return the validated contract for ``sheet_path``.

        Use this first to discover the available fields, primary key,
        and which fields are derived. Combine with ``query`` or
        ``list_records`` for actual data access.
        """
        sheet = _open(sheet_path)
        return sheet.contract.model_dump(mode="json", by_alias=True)

    @mcp.tool
    def query(
        sheet_path: str,
        sql: str,
        params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run a SELECT-only DuckDB query against ``records``.

        Prefer this over ``list_records`` for COUNT, GROUP BY, MIN/MAX,
        and other aggregations so you do not pull every row into the
        agent's context. Use ``?`` placeholders + ``params`` for any
        user-provided value.
        """
        return _open(sheet_path).query(sql, params)

    @mcp.tool
    def list_records(
        sheet_path: str,
        filter: str | None = None,
        fields: list[str] | None = None,
        limit: int = 50,
        cursor: str | None = None,
        params: list[Any] | None = None,
        format: Literal["json", "toon"] = "json",
    ) -> dict[str, Any]:
        """List records page by page.

        Always pass ``fields`` to project only the columns you need.
        Use ``filter`` (a DuckDB WHERE-clause) plus ``params`` for
        condition values. ``format='toon'`` returns a token-efficient
        TOON string in ``records`` instead of a JSON list.
        """
        return _open(sheet_path).list_records(
            filter=filter,
            fields=fields,
            limit=limit,
            cursor=cursor,
            params=params,
            format=format,
        )

    @mcp.tool
    def get_record(
        sheet_path: str,
        id: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Fetch one record by primary key. Returns ``null`` if missing."""
        return _open(sheet_path).get_record(id, fields=fields)

    @mcp.tool
    def upsert_records(
        sheet_path: str,
        records: list[dict[str, Any]],
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Insert or update records by primary key.

        ``actor`` is required (or set ``--actor`` on the server start).
        ``editable_by`` patterns on the contract are enforced.
        """
        return _open(sheet_path, actor=actor).upsert_records(records)

    @mcp.tool
    def delete_records(
        sheet_path: str,
        ids: list[str],
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Delete records by primary key id."""
        return _open(sheet_path, actor=actor).delete_records(ids)

    @mcp.tool
    def materialize(
        sheet_path: str,
        targets: list[str] | None = None,
        record_ids: list[str] | None = None,
        force: bool = False,
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Materialize derived fields. Returns the §10.6 envelope.

        Combine with ``materialization_status`` to inspect what is
        stale before running. ``force=True`` recomputes even when the
        cache and ``human_override`` say otherwise.
        """
        return _open(sheet_path, actor=actor).materialize(
            targets=targets,
            record_ids=record_ids,
            force=force,
            ai_client=ai_client,
        )

    @mcp.tool
    def materialization_status(
        sheet_path: str,
        targets: list[str] | None = None,
    ) -> dict[str, Any]:
        """Per-target counts (ai / import / human_override) and last run."""
        return _open(sheet_path).materialization_status(targets=targets)

    @mcp.tool
    def provenance(
        sheet_path: str,
        record_id: str,
        field: str,
        history: bool = False,
    ) -> Any:
        """Return the latest provenance entry, or the full append-only history."""
        return _open(sheet_path).provenance(
            record_id=record_id,
            field=field,
            history=history,
        )

    # ------------------------------------------------------------------
    # Per-sheet skills surfaced as MCP prompts.
    #
    # Each `<root>/<sheet>/skills/<skill>.md` becomes a prompt named
    # `<sheet-id>:<skill-name>`. Prompt arguments are the skill's
    # declared `arguments`; `prompts/get` renders the markdown body
    # with substitutions filled in.
    _register_skills_as_prompts(mcp, root_path)

    return mcp


def _register_skills_as_prompts(mcp: FastMCP, root_path: Path) -> None:
    """Walk every sheet under ``root_path`` and register its skills as prompts.

    Skip silently if a sheet has no ``skills/`` directory. If a skill
    file is malformed, the SkillError is logged-and-skipped so one
    broken skill does not bring down the whole server.
    """
    import logging

    log = logging.getLogger("folio_mcp.skills")

    for sheet_dir in sorted(root_path.iterdir()):
        if not sheet_dir.is_dir():
            continue
        if not (sheet_dir / "contract.yaml").is_file():
            continue
        try:
            sheet = open_sheet(sheet_dir)
        except FolioError as exc:
            log.warning("MCP: skipping %s — %s", sheet_dir.name, exc)
            continue
        try:
            skills = load_skills(sheet_dir)
        except SkillError as exc:
            log.warning("MCP: skipping skills under %s — %s", sheet_dir.name, exc)
            continue

        for skill in skills:
            _register_one_skill_prompt(mcp, sheet.contract.id, skill)


def _register_one_skill_prompt(mcp: FastMCP, sheet_id: str, skill: Skill) -> None:
    """Register a single skill as ``<sheet-id>:<skill-name>``."""
    prompt_name = f"{sheet_id}:{skill.name}"

    declared_required = [a for a in skill.arguments if a.required]
    declared_optional = [a for a in skill.arguments if not a.required]

    def renderer(**kwargs: str) -> str:
        return skill.render(kwargs)

    # FastMCP reads the function signature to surface argument names to
    # MCP clients. Build a synthetic signature so the prompt advertises
    # the same arguments the skill declares.
    import inspect

    parameters = [
        inspect.Parameter(
            a.name,
            inspect.Parameter.KEYWORD_ONLY,
            annotation=str,
        )
        for a in declared_required
    ] + [
        inspect.Parameter(
            a.name,
            inspect.Parameter.KEYWORD_ONLY,
            default="",
            annotation=str,
        )
        for a in declared_optional
    ]
    renderer.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        parameters=parameters,
        return_annotation=str,
    )
    renderer.__name__ = prompt_name.replace(":", "_").replace("-", "_")
    renderer.__doc__ = skill.description
    # pydantic's typing.get_type_hints() reads __annotations__, not the
    # __signature__ we just attached. Mirror the parameter annotations
    # so the introspection that FastMCP performs sees the right types.
    renderer.__annotations__ = {a.name: str for a in skill.arguments}
    renderer.__annotations__["return"] = str

    mcp.prompt(name=prompt_name, description=skill.description)(renderer)


__all__ = ["build_server"]
