# Phase 3 — MCP Server and TOON Output

The fourth executable slice of Folio. Phase 3 makes a Folio sheet
addressable by AI agents over Anthropic-style MCP and adds the
token-efficient TOON wire format for `list_records`.

```
folio-mcp serve --root <directory-of-sheets>
```

```
GET list_records(format=toon)
→ {"records": "<TOON-encoded string>", "format": "toon", ...}
```

## In scope

### MCP server (`folio-mcp` package)

- `src/folio_mcp/server.py` using `FastMCP` (named in design
  overview §20). The server exposes the nine SDK operations as MCP
  tools with docstrings that include "when to use" and "how to
  combine" guidance for agents (per design overview §18 example).
- Tool surface (one tool per operation): `get_contract`, `query`,
  `list_records`, `get_record`, `upsert_records`, `delete_records`,
  `materialize`, `materialization_status`, `provenance`. Every tool
  takes a `sheet_path` (or `sheet_id`) argument that the server
  resolves against a configured root directory.
- Server-side configuration:
  - `--root <path>` to a directory containing one or more sheets.
  - `--actor <string>` default actor for write tools when callers
    do not supply one.
  - `--bind 127.0.0.1` (default, MCP runs locally).
- `[project.scripts]` registers `folio-mcp = "folio_mcp.cli:main"`.
- Pydantic input models per tool so MCP clients see typed
  parameters; outputs match the SDK return shapes.

### TOON output

- `src/folio/_toon.py` thin TOON encoder covering the JSON subset
  Folio actually returns from `list_records`: arrays of objects with
  scalar / array / object values.
- `Sheet.list_records(..., format="toon")` returns the records as a
  TOON string instead of a JSON list. The envelope still reports
  `format: "toon"` and `next_cursor` per §10.5.
- CLI: `folio list <sheet> --format toon` emits the TOON string
  (records key) plus the JSON envelope around it.
- The encoder is intentionally narrow; extension types (binary,
  large nested unions) are deferred.

## Out of scope (deferred to later phases)

- Streaming MCP responses for paginated `list_records`. The MCP
  server returns one envelope per call; pagination is handled by
  the cursor.
- Multi-sheet routing in MCP. `--root` resolves a single tree;
  multi-workspace tooling lands with Phase 6.
- Authentication beyond local bind. Out of scope per §19.1
  reasoning (Viewer is local-only and the MCP server inherits the
  same posture for now).
- A Node.js MCP server. The `folio-mcp` package ships in Python only.

## Verification expectations

- TOON encoder tests covering: empty list, scalar values, nested
  arrays / objects, strings with quotes, integers vs floats,
  null handling, and round-trip stability for representative
  Folio records.
- MCP tool tests using `FastMCP`'s in-process client harness:
  - `get_contract`, `query`, `list_records` (json + toon),
    `get_record` against a temp sheet.
  - Write tools with an explicit actor.
  - `materialize` against a stubbed `AIClient` (reuses the Phase 1
    `StubAIClient` plumbing via the MCP server's `--ai-stub` flag,
    which is itself a test-only surface).
- CLI smoke: `scripts/smoke-mcp.sh` runs `folio-mcp` against a temp
  sheet, calls every tool through the in-process MCP client, and
  asserts the expected outputs.

## Reference scenario (target behavior)

```python
from fastmcp.client import Client
from folio_mcp.server import build_server

server = build_server(root="./sheets", default_actor="agent:demo")
async with Client(server) as client:
    rows = await client.call_tool(
        "query",
        {"sheet_path": "customers",
         "sql": "SELECT industry_tag, COUNT(*) AS n FROM records GROUP BY 1"},
    )
    listed = await client.call_tool(
        "list_records",
        {"sheet_path": "customers", "format": "toon", "limit": 3},
    )
    # listed["records"] is a TOON string; listed["format"] == "toon".
```

## Suggested implementation breakdown

- **`FOLIO-H-017`**: `folio-mcp` package, `FastMCP` server wiring,
  per-tool Pydantic models, in-process MCP tests, and a deterministic
  `scripts/smoke-mcp.sh` behind `make verify`.
- **`FOLIO-H-018`**: `src/folio/_toon.py` encoder, `format="toon"`
  on `list_records`, the `--format toon` CLI option, and
  encoder-spec tests.

## Related

- Canonical specification: [`../design-docs/overview.md`](../design-docs/overview.md) §15, §18, §10.5
- TOON format: <https://github.com/toon-format/toon>
