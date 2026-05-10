# Folio Desktop — Python runtime bundling

**Decision:** the Folio Desktop app (`apps/desktop/`) does **not** bundle a
Python interpreter. It launches the host's `folio-viewer` Python CLI and
displays an actionable install prompt if the CLI is not on PATH.

This document explains why, what was rejected, and how the desktop app
finds the runtime.

## Context

The desktop app is an Electron wrapper that spawns the existing
FastAPI-based `folio-viewer` server and points a `BrowserWindow` at it
(`apps/desktop/src/main/server-manager.ts`). The renderer is the same
React build the standalone Viewer ships, served by the Python process
itself. So the question is purely: **how does the user's machine end up
with a runnable `folio-viewer` binary?**

## Options considered

### A. PyInstaller `--onedir` per OS

Bundle `folio-viewer` as a frozen executable, one per (OS × arch),
included in `extraResources/`.

- **Pros:** truly zero-prerequisite first launch.
- **Cons:**
  - PyInstaller has known issues with DuckDB's bundled `.so` /
    `.dll` paths and with FastAPI's runtime imports (uvicorn worker
    classes loaded by string).
  - A Python derivation script that declares `scripts/requirements.txt`
    spawns `python -m venv` from the running interpreter. A frozen
    PyInstaller bundle cannot create a normal venv — the embedded
    interpreter is not a regular CPython on the path that `venv`
    expects.
  - The release matrix grows by one OS-specific bundle per platform.

### B. Embedded standalone Python (e.g. `python-build-standalone`)

Bundle the official PEP-711-style standalone Python distribution
(<https://github.com/astral-sh/python-build-standalone>) into
`extraResources/python/`, then `pip install folio` into that copy at
package time. The desktop app launches `extraResources/python/bin/python -m folio_viewer.cli ...`.

- **Pros:** true zero-prerequisite, `python -m venv` works (it is a
  real CPython), no PyInstaller quirks.
- **Cons:** ~30 MB compressed per OS. Need to keep the bundled Python
  patched. Codesigning gets harder on macOS (the bundle ships hundreds
  of dylibs that all need ad-hoc-or-real signatures).

### C. Require host Python (chosen)

Document `pipx install folio` (or any equivalent) as a prerequisite.
The desktop app probes `FOLIO_VIEWER_BIN` ⇒ `<repo>/.venv/bin/folio-viewer`
⇒ `PATH` (in that order) and surfaces a clear error dialog when none
of the candidates resolves to a runnable binary.

## Why C

1. **Right shape for v1.** The desktop app is a thin GUI shell over a
   well-defined CLI. Folio's whole identity is "small specification +
   reference implementation"; pushing a 100 MB Electron + Python +
   sidecar bundle as v1 conflicts with that.
2. **Per-sheet venvs work.** A sheet with `scripts/requirements.txt`
   needs a real Python on the system to create
   `<user-cache>/folio/<sheet-id>/runtime/venv/`. Option (B) covers
   this; (A) does not. (C) defers the problem to the user's existing
   Python — which they were going to need for `python` derivations
   anyway.
3. **Reversible.** Switching from (C) to (B) later is a packaging
   concern, not a contract change. The renderer never sees the
   difference.
4. **Smaller surface.** No second packaging pipeline, no PyInstaller
   spec file, no DuckDB import audit, no per-OS frozen-bundle
   regressions to chase.

The cost is a friction-y first launch. We mitigate it with:

- A native dialog when the binary is missing, naming the candidate
  paths checked and pointing at the canonical install instructions.
- A "How to install" entry in the macOS "Sheet" menu opens the docs
  page in the browser.

## Resolution order

`apps/desktop/src/main/main.ts:findFolioBin()`:

1. `process.env.FOLIO_VIEWER_BIN` (explicit override).
2. `<repoRoot>/.venv/bin/folio-viewer` (developer mode — the user is
   running from the source checkout with `uv sync` already done).
3. The literal string `folio-viewer` (resolved against `PATH` by the
   OS).

If `spawn` fails with `ENOENT`, the app shows a dialog and stays
minimized rather than quitting, so the user can install Folio and
retry from the menu.

## Re-evaluation triggers

- More than one user reports failed first launch in two consecutive
  weeks → revisit Option B.
- macOS notarization complains about the app having no signed code
  (Electron itself is signed; the spawned `folio-viewer` is unsigned
  but external) → revisit Option B.
- The release matrix ever needs to ship for a platform without
  user-installable Python (very unlikely, but mobile / sandboxed
  app stores would force this).

## Status

**Accepted, 2026-05-11.** The app already implements the lookup chain
in §"Resolution order". The remaining work is the install-prompt
dialog and the Sheet-menu link, tracked under Task #43 (the
`release-desktop.yml` rollout).
