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

## Install

Releases ship three artifact families. Pick the one that matches how you
want to use Folio.

### Python (CLI + SDK + MCP server + Viewer backend)

```bash
# from PyPI once published (preferred)
pipx install folio
uv tool install folio

# from a tagged GitHub Release wheel
pipx install https://github.com/nyuta01/folio/releases/download/vX.Y.Z/folio-X.Y.Z-py3-none-any.whl
```

The wheel installs three console scripts: `folio`, `folio-mcp`,
`folio-viewer`. SHA-256 checksums for every release artifact are
attached as `SHA256SUMS.txt`.

### Folio Desktop (Electron wrapper)

Download the installer for your platform from the
[latest release](https://github.com/nyuta01/folio/releases/latest):

| Platform | Asset |
|---|---|
| macOS (Apple Silicon) | `Folio-X.Y.Z-arm64.dmg` |
| macOS (Intel) | `Folio-X.Y.Z.dmg` |
| Windows | `Folio Setup X.Y.Z.exe` (or `Folio-X.Y.Z-portable.exe`) |
| Linux | `Folio-X.Y.Z.AppImage` (or `folio_X.Y.Z_amd64.deb`) |

The desktop app shells out to the host's `folio-viewer` Python CLI; if
it is missing, the launcher offers an "Open install docs" button. See
[`docs/methodology/desktop-runtime.md`](docs/methodology/desktop-runtime.md)
for the rationale.

### Documentation site

Browse [the Folio docs](https://nyuta01.github.io/folio/) or build them
locally:

```bash
cd apps/docs
npm install
npm run dev      # → http://127.0.0.1:4321/
```

The site is auto-deployed to GitHub Pages on every push to `main` that
touches `apps/docs/`.

## Releases

A maintainer cuts a release by pushing a tag of the form `vX.Y.Z`:

```bash
make verify             # CI gate locally
git tag v0.2.0
git push origin v0.2.0
```

Two workflows then fire:

- **`release-python.yml`** builds `dist/folio-*.whl` + `dist/folio-*.tar.gz`,
  smoke-tests the wheel in a clean venv, and attaches both plus a
  `SHA256SUMS.txt` to a draft GitHub Release.
- **`release-desktop.yml`** builds `viewer/dist/`, then runs
  `electron-builder` on macOS / Windows / Linux runners, attaching DMG,
  Setup, AppImage, and zip artifacts to the same draft Release.

The release stays in **draft** until a human flips it to **Published**.
Full procedure in
[`docs/methodology/release.md`](docs/methodology/release.md).

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
