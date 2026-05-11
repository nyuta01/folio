# Folio

[![PyPI](https://img.shields.io/pypi/v/folio-kit?label=folio-kit)](https://pypi.org/project/folio-kit/)
[![npm](https://img.shields.io/npm/v/folio-agent-skills?label=folio-agent-skills)](https://www.npmjs.com/package/folio-agent-skills)
[![Python](https://img.shields.io/pypi/pyversions/folio-kit)](https://pypi.org/project/folio-kit/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![verify](https://img.shields.io/github/actions/workflow/status/nyuta01/folio/verify.yml?branch=main&label=verify)](https://github.com/nyuta01/folio/actions/workflows/verify.yml)

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
- [Examples](examples/README.md) — five sheets covering four canonical use cases (customers + its customer-revenue sidecar, research-notes, research-memory, onboarding) — all run offline

## Quickstart

```bash
uv tool install folio-kit          # → installs the `folio` command

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
# from PyPI (preferred)
pipx install folio-kit
uv tool install folio-kit

# from a tagged GitHub Release wheel
pipx install https://github.com/nyuta01/folio/releases/download/vX.Y.Z/folio_kit-X.Y.Z-py3-none-any.whl
```

The PyPI distribution name is `folio-kit`; the wheel installs three
console scripts: `folio`, `folio-mcp`, `folio-viewer`. SHA-256
checksums for every release artifact are attached as `SHA256SUMS.txt`.

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

#### First-launch warning (unsigned builds)

Folio Desktop ships **unsigned and un-notarized** today. Both macOS
Gatekeeper and Windows SmartScreen will warn on first launch. This is
expected — the workarounds below are safe; signing and notarization
are tracked as a release follow-up.

**macOS** — *"Apple は、"Folio" にマルウェアが含まれていないことを検証できませんでした"* / *"Apple could not verify that "Folio" is free of malware"*:

```bash
# 1. Drag Folio.app into /Applications first.
# 2. Then strip the quarantine attribute Chrome / Safari put there:
xattr -dr com.apple.quarantine /Applications/Folio.app
open /Applications/Folio.app
```

Or, without Terminal: right-click `Folio.app` in Finder → **Open** →
confirm in the dialog. After that, normal double-click works.

If macOS shows *"Folio was blocked"* in **System Settings → Privacy &
Security**, scroll to the bottom and click **Open Anyway**.

**Windows** — *"Microsoft Defender SmartScreen prevented an
unrecognized app from starting"*:

Click **More info** → **Run anyway**. Or use the portable
`Folio.X.Y.Z.exe` and approve the unverified-publisher prompt.

**Linux** — `.AppImage` works without prompts; `.deb` is unsigned:

```bash
chmod +x Folio-X.Y.Z.AppImage
./Folio-X.Y.Z.AppImage

# or for the .deb:
sudo dpkg -i folio-desktop_X.Y.Z_amd64.deb
```

**Verifying the download** — every release ships
`SHA256SUMS-{macos-arm64,linux-x64,windows-x64}.txt`. Compare locally:

```bash
shasum -a 256 Folio-X.Y.Z-arm64.dmg     # macOS / Linux
certutil -hashfile "Folio Setup X.Y.Z.exe" SHA256   # Windows
```

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

- **`release-python.yml`** builds `dist/folio_kit-*.whl` + `dist/folio_kit-*.tar.gz`,
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
