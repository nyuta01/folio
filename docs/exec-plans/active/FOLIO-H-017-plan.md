# FOLIO-H-017 Plan: MCP Server

## Goal

Make a Folio sheet addressable to AI agents through Anthropic-style
MCP by shipping `folio-mcp`, a sibling Python package that exposes
the nine SDK operations as MCP tools.

## Scope

- New top-level package `src/folio_mcp/` with:
  - `__init__.py` re-exporting `build_server`.
  - `server.py` with `build_server(*, root, default_actor=None,
    ai_client=None) -> FastMCP` returning a configured FastMCP
    instance. Each of the nine SDK operations becomes one tool with
    a docstring that includes "when to use" / "how to combine"
    guidance for agents.
  - `cli.py` with a `folio-mcp serve --root <path> [--actor <a>]
    [--bind 127.0.0.1] [--port <n>]` command.
- `pyproject.toml` adds `fastmcp>=2.6` to runtime dependencies and
  registers `folio-mcp = "folio_mcp.cli:main"` as a project script.
- Tools (one per SDK op): `get_contract`, `query`, `list_records`,
  `get_record`, `upsert_records`, `delete_records`, `materialize`,
  `materialization_status`, `provenance`. Each accepts a
  `sheet_path` string that the server resolves against `--root`.
  Path traversal that escapes `root` is rejected.
- Output values flow back as JSON-serializable dicts. Contract
  models use `model_dump(mode="json", by_alias=True)` so MCP
  clients see ODCS-style `apiVersion` / `primaryKey` keys.
- `tests/test_mcp.py` covers each tool using FastMCP's in-process
  `Client` harness through `asyncio.run()`. Materialize tests inject
  `StubAIClient`.
- `scripts/_mcp_smoke.py` builds a temp sheet under a root, builds
  the server with a `StubAIClient`, and walks every tool through
  the in-process client. `scripts/smoke-mcp.sh` invokes the
  harness so the gate stays offline.
- `Makefile` adds `mcp-smoke` and includes it in `verify`.
- `scripts/harness_check.py` requires the new package, tests, smoke
  files, and the `mcp-smoke` Makefile line.

## Out of scope

- Streaming / cursor-aware pagination at the MCP layer. Pagination
  follows the SDK envelope (`next_cursor`).
- Multi-workspace routing across roots. Phase 6.
- Authentication beyond local-bind. Same posture as the Viewer.

## Evidence

- `make verify` passes locally with the expanded `python-test` and
  the new `mcp-smoke`.
- Every tool round-trips against an in-process FastMCP `Client`
  without a live API key.

## Observation

Phase 3 has been spec'd, and the Phase 1 SDK already exposes the
nine operations the MCP server needs to surface. Without this
task, agents that talk MCP cannot operate Folio sheets.

## Decision

- Build atop FastMCP because it is the library named in design
  overview §20 and supports an in-process client harness so tests
  stay offline.
- Inject the AI client via a `build_server` argument (mirroring the
  `Sheet.materialize` shape from `FOLIO-H-012`). Production callers
  pass nothing and the default `AnthropicClientAdapter` is used;
  tests pass `StubAIClient`.
- Reject `sheet_path` that resolves outside the configured root so
  a misconfigured agent cannot escape into the local filesystem.
- Use synchronous Python tools and let FastMCP wrap them; this
  matches the rest of the SDK's sync surface and keeps the test
  harness simple (`asyncio.run`).

## Permanent Fix

- `make verify` runs the in-process MCP smoke. Removing a tool or
  breaking a docstring contract surfaces in CI.
- `scripts/harness_check.py` requires the new package, the new
  test, and the smoke pair.

## Next Check

`FOLIO-H-020` adds extension kinds; the MCP server's
`materialize` tool already routes through `Sheet.materialize` so it
will inherit the new kinds without further work.
