# FOLIO-H-031 Plan: Remove MCP Server Surface

## Goal

Remove the unnecessary `folio-mcp` server surface instead of keeping an
unauthenticated network tool server around with safer documentation. Folio's
supported agent path is CLI + sheet-local skills; integrations use the Python
SDK directly.

## Scope

- Remove `src/folio_mcp`, the `folio-mcp` console script, and the FastMCP
  runtime dependency.
- Remove MCP-specific tests and smokes from `make verify`.
- Remove user-facing MCP docs and navigation.
- Update the canonical spec, design overview, README, PyPI README, product
  specs, quality score, failure log, and agent handoff state.
- Add a deterministic drift invariant that rejects reintroducing the MCP
  package, docs, dependency, console script, or smoke target.

## Out of scope

- Replacing MCP with another hosted/network agent API.
- Removing the CLI, SDK, Viewer, or sheet-local skill system.

## Observation

The Aardvark finding came from docs recommending `folio-mcp` HTTP bound to all
interfaces for remote agents. Local inspection showed no core product path
depended on MCP: the CLI, SDK, Viewer, Desktop, and examples can operate without
the MCP server. Since the CLI already covers the intended agent path and keeps
actions auditable, retaining a generic unauthenticated HTTP tool surface was
unnecessary risk.

## Decision

Retire MCP completely. This removes both the unsafe HTTP deployment path and
the optional stdio MCP server, keeping Folio smaller and aligned with the
file-first trust model.

## Permanent Fix

`folio-mcp`, `src/folio_mcp`, FastMCP, MCP docs, MCP tests, and `mcp-smoke` are
removed. `scripts/harness_drift.py` now fails if the removed package, docs,
dependency, console script, or smoke target is reintroduced.

## Next Check

Run `make verify` and the docs build. Future agent-interface work should start
from the CLI or SDK and add explicit authentication before introducing any
network-facing tool server.
