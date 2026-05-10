# Folio

Portable, AI-native data sheets.

A **sheet** is a directory of plain files that AI agents can read and write as
first-class users, that humans can review later, and that can be carried as a
`tar` archive across machines.

```
my-sheet/
  contract.yaml         # required: ODCS-subset structure declaration
  records.jsonl         # required: data (may be empty)
  README.md             # optional: AI frontmatter + human docs
  derivations/          # optional: per-field derivation YAML
  scripts/              # optional: reusable scripts (any language)
  attachments/          # optional: binary attachments
  provenance.jsonl      # optional: auto-generated lineage
  datapackage.json      # optional: Frictionless Data Package descriptor
```

This repository will provide:

- `folio` — Python SDK + CLI (reference implementation).
- `folio-mcp` — MCP server that exposes SDK operations as tools.
- `folio-viewer` — local-only Viewer (FastAPI + React).

## Status

Pre-implementation. The repository currently holds the design document and
the AI-first engineering harness. See:

- [Design overview](docs/design-docs/overview.md)
- [Phase 0 product spec](docs/product-specs/phase-0-minimum-sheet.md)
- [Agent guide](AGENTS.md)

## Repository Harness

This repository follows an AI-first operating model. The harness is a small
set of compact docs, structured task state, and deterministic checks that let
coding agents do reliable, restartable work.

```bash
make agent-init   # restart context for the next agent
make verify       # the single verification gate
```

`make verify` currently runs `harness-check`, `drift-check`, and
`validate-docs`. Phase-specific checks (Python tests, CLI smoke, MCP smoke,
Viewer smoke) will be added behind the same target as implementation lands.

See [docs/methodology/harness-engineering.md](docs/methodology/harness-engineering.md)
for the full operating model.
