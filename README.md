# Folio

Portable, AI-native data sheets.

A **sheet** is a directory of plain files that AI agents read and write as
first-class users, that humans review later, and that travel as a `tar`
archive across machines.

```
my-sheet/
├── contract.yaml         # required — ODCS subset
├── records.jsonl         # required — one JSON object per line
├── derivations/          # optional — derivation files
├── scripts/              # optional — reusable scripts
├── provenance.jsonl      # append-only audit log
└── README.md             # optional, with typed frontmatter
```

## Surfaces

- **`folio`** — Python SDK + CLI (validate, query, list, upsert, delete,
  materialize, status, provenance, serve, script, export).
- **`folio-mcp`** — FastMCP server exposing the SDK as nine tools (stdio
  or HTTP transport).
- **`folio-viewer`** — local-only FastAPI + React UI for human review.

## Documentation

User-facing documentation lives in [`apps/docs/`](apps/docs/) (Astro +
Starlight). Run it locally:

```bash
cd apps/docs
npm install
npm run dev      # → http://127.0.0.1:4321/
```

Or read the canonical sources directly:

- [Design overview](docs/design-docs/overview.md) — the spec
- [ADRs](docs/design-docs/adrs/README.md) — architectural decisions
- [Examples](examples/README.md) — four use-case sheets that run offline

## Quickstart

```bash
uv tool install folio

folio validate examples/customers
folio materialize examples/customers --actor agent:demo
folio serve examples/customers --port 3000 --actor agent:human
# → http://127.0.0.1:3000/
```

## Repository harness

This repo follows an AI-first operating model: compact router docs,
structured task state, and a single deterministic verification gate.

```bash
make agent-init   # restart context for the next agent
make verify       # harness-check + drift-check + validate-docs
                  # + pytest + 6 smokes (cli, materialize, scripts,
                  #   mcp, extension-kinds, viewer)
```

See [`AGENTS.md`](AGENTS.md) and
[`docs/methodology/harness-engineering.md`](docs/methodology/harness-engineering.md)
for the full operating model.
