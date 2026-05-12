# Phase 3 — TOON Output

The fourth executable slice of Folio. Phase 3 adds the token-efficient TOON
wire format for `list_records`.

```
GET list_records(format=toon)
-> {"records": "<TOON-encoded string>", "format": "toon", ...}
```

## In scope

### TOON output

- `src/folio/_toon.py` thin TOON encoder covering the JSON subset Folio
  actually returns from `list_records`: arrays of objects with scalar / array /
  object values.
- `Sheet.list_records(..., format="toon")` returns the records as a TOON string
  instead of a JSON list. The envelope still reports `format: "toon"` and
  `next_cursor` per §10.5.
- CLI: `folio list <sheet> --format toon` emits the TOON string (`records` key)
  plus the JSON envelope around it.
- The encoder is intentionally narrow; extension types (binary, large nested
  unions) are deferred.

## Removed Surface

The Phase 3 MCP server was removed by `FOLIO-H-031`. Folio's supported agent
path is now CLI + sheet-local skills, and integrations should use the Python SDK
directly. The project no longer ships `folio-mcp`, `src/folio_mcp`, FastMCP
runtime dependencies, MCP docs, or MCP smoke tests.

## Verification expectations

- TOON encoder tests covering: empty list, scalar values, nested arrays /
  objects, strings with quotes, integers vs floats, null handling, and
  round-trip stability for representative Folio records.
- CLI smoke coverage through `folio list --format toon` and the ordinary
  `make verify` gate.

## Suggested implementation breakdown

- **`FOLIO-H-017`**: superseded by `FOLIO-H-031`; the MCP package was removed.
- **`FOLIO-H-018`**: `src/folio/_toon.py` encoder, `format="toon"` on
  `list_records`, the `--format toon` CLI option, and encoder-spec tests.

## Related

- Canonical specification: [`../design-docs/overview.md`](../design-docs/overview.md) §15, §18, §10.5
- TOON format: <https://github.com/toon-format/toon>
