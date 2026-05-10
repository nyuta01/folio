# FOLIO-H-016 Plan: Phase 3 Product Spec and Backlog

## Goal

Record the executable shape of Phase 3 (MCP server + TOON output) and
break the work into bounded backlog tasks.

## Scope

- New product spec at
  `docs/product-specs/phase-3-mcp-server-and-toon-output.md`.
- Updated `docs/product-specs/README.md` index.
- Two backlog tasks:
  - `FOLIO-H-017` — `folio-mcp` package, `FastMCP`-based server
    exposing the nine SDK operations as MCP tools, in-process MCP
    tests, and `scripts/smoke-mcp.sh`.
  - `FOLIO-H-018` — `src/folio/_toon.py` encoder, `format="toon"`
    on `list_records`, the `--format toon` CLI option, and
    encoder-spec tests.

## Out of scope

- Implementing any Phase 3 code; that is `FOLIO-H-017` and
  `FOLIO-H-018`.
- Streaming MCP responses or multi-sheet routing in MCP. Tracked
  inside the spec as out-of-scope notes.
- Authentication beyond local-bind. Same posture as the Viewer (§19).

## Evidence

- `make verify` passes after the spec and feature-list updates.
- `make validate-docs` accepts the new local link.

## Observation

Phase 1 made the Folio sheet AI-native; Phase 3 makes it addressable
to AI agents through a standard protocol (MCP) and adds the
token-efficient TOON wire format that the design overview §16, §18,
and §10.5 already commit to. Implementation loops need a spec they
can land without re-reading the design overview.

## Decision

Mirror the Phase 1 / Phase 2 spec format. Split implementation into
exactly two tasks: the MCP server (a new top-level package) and the
TOON output (a small change inside `folio.list_records`). They are
independent enough to land in either order, but `H-017` is the
primary scope and `H-018` is a smaller follow-up.

## Permanent Fix

- `make validate-docs` enforces local-link integrity for the new
  spec.
- The Phase 3 spec calls out the `--ai-stub` test-only flag for the
  MCP server so future agents do not introduce ambient stub mode.

## Next Check

Begin `FOLIO-H-017` (MCP server) once Phase 3 work starts. Its plan
should record the per-tool Pydantic input models and how the
server resolves `sheet_path` against `--root`.
