# Folio release procedure

This document is the runbook for cutting a Folio release. It is a
handful of human-operated steps wrapped around two CI workflows; the
artifacts ship through GitHub Releases.

## What ships

A release publishes three artifact families under one git tag
`vMAJOR.MINOR.PATCH`:

| Artifact | Built by | Workflow |
|---|---|---|
| `folio-X.Y.Z-py3-none-any.whl` | `make dist` (`uv build`) | `release-python.yml` |
| `folio-X.Y.Z.tar.gz` (sdist) | `make dist` | `release-python.yml` |
| `Folio-X.Y.Z-arm64.dmg` / `Folio-X.Y.Z.dmg` (mac) | `electron-builder --mac` | `release-desktop.yml` |
| `Folio Setup X.Y.Z.exe` / portable exe (win) | `electron-builder --win` | `release-desktop.yml` |
| `Folio-X.Y.Z.AppImage` / `folio_X.Y.Z_amd64.deb` (linux) | `electron-builder --linux` | `release-desktop.yml` |
| `SHA256SUMS.txt` (per-pipeline) | `shasum` in workflow | both |

Documentation deploys are independent of releases: pushes to `main`
that touch `apps/docs/` redeploy GitHub Pages via `release-docs.yml`.

## Before you tag

1. **Update versions** in lockstep:
   - `pyproject.toml` → `[project] version = "X.Y.Z"`
   - `apps/desktop/package.json` → `"version": "X.Y.Z"`
   - `viewer/package.json` → `"version": "X.Y.Z"` (cosmetic but kept aligned)
2. **If the data format changed**, bump `SPECIFICATION.md`'s status
   line and append a release note. A breaking change to the data
   format requires a major version bump.
3. **Run the gate locally:** `make verify`. It must pass.
4. **Run the wheel smoke explicitly:** `make dist-check`.
5. **Run the desktop pack smoke:**
   `npm --prefix viewer run build && npm --prefix apps/desktop run pack`.
   Confirm `apps/desktop/out/mac-*/Folio.app/Contents/Resources/viewer-dist/index.html`
   exists and that double-clicking the `.app` launches the picker.
6. **Update `AGENT_PROGRESS.md`** and the changelog (when one exists)
   with the user-visible changes since the previous tag.
7. **Open a PR** with the version bumps; merge it cleanly.

## Tag and push

```bash
git switch main
git pull --ff-only
git tag vX.Y.Z
git push origin vX.Y.Z
```

Pushing the tag fires both `release-python.yml` and
`release-desktop.yml`. The Python pipeline takes ~3 minutes; the
Desktop pipeline takes ~10–15 minutes (Electron download dominates).

## After the workflows finish

1. Open <https://github.com/nyuta01/folio/releases>. The new tag has a
   **draft** Release with all artifacts attached.
2. Verify the asset list contains, at minimum:
   - one `.whl`, one `.tar.gz`, one `SHA256SUMS.txt` (Python pipeline),
   - one `.dmg` per macOS architecture,
   - one Windows `.exe`,
   - one Linux `.AppImage` (and optionally `.deb`),
   - one `SHA256SUMS-<platform>-<arch>.txt` per OS bucket.
3. Spot-check at least one artifact:
   - Download the wheel, `pipx install ./folio_kit-X.Y.Z-py3-none-any.whl`
     into a fresh venv, run `folio --help`.
   - Download the macOS DMG (or AppImage on Linux), run it, open the
     `examples/customers` sheet, confirm the grid renders and a
     materialize round-trip succeeds.
4. **Edit the auto-generated release notes** to highlight notable
   changes; the GitHub-generated changelog is a starting point, not
   the final copy.
5. Flip the Release from **Draft** to **Published**. This automatically
   triggers `release-python.yml` again for PyPI trusted publishing. The
   publish path checks out the release tag, rebuilds the wheel and sdist,
   runs `make dist-check`, downloads only the artifacts from that same
   workflow run, and then uploads them to PyPI via OIDC. It deliberately
   does **not** publish mutable GitHub Release assets. Once the job is green,
   `uv tool install folio-kit` will pick up the new version.

If a smoke fails, **delete the draft Release** (not the tag) and fix
forward by tagging `vX.Y.Z+1` or `vX.Y.Z-rc.2`. We do not edit
published releases.

## Pre-releases

Tags containing a hyphen (e.g. `v0.2.0-rc.1`) flip the Release to
prerelease automatically (both workflows check
`contains(github.ref_name, '-')`). Use prereleases to validate
artifacts on a wider matrix before promoting to a stable version.

## Rollback

If a published release ships a critical bug:

1. Tag `vX.Y.Z+1` (or `vX.Y.Z-hotfix`) with the fix.
2. Edit the broken release's notes to point readers at the new tag.
3. Do **not** delete the broken artifacts — they have been mirrored;
   removing them breaks deterministic install pipelines.

## Failure modes and responses

- **`release-python.yml` fails on smoke.** The wheel is uninstallable.
  Investigate locally with `make dist-check`. Fix in `main`, retag.
- **`release-desktop.yml` fails on one OS.** Other OS artifacts will
  still upload to the draft Release; do not publish until you have
  a complete set or have explicitly accepted a partial release in the
  notes.
- **`SHA256SUMS.txt` is missing.** The shasum step runs only when at
  least one installer was produced. If the matrix produced nothing,
  the upstream build failed — read the workflow logs.
- **Pages deploy fails.** Independent of releases. Re-run
  `release-docs.yml` from the Actions UI.

## One-time setup: GitHub social preview

The OG card at `apps/docs/public/og-image.png` is what surfaces when
the **docs URL** is shared (Twitter, Slack, Discord, LinkedIn). The
**repo URL** uses a separate image that has to be uploaded by hand:

1. Open `https://github.com/nyuta01/folio/settings`.
2. Scroll to **Social preview**.
3. Upload `apps/docs/public/og-image.png` (1200×630 PNG).

This is a manual one-time step; subsequent commits do not need to
re-upload unless the artwork changes.

## Out of scope (today)

- macOS notarization and Windows Authenticode signing (planned;
  artifacts ship unsigned for now and macOS users see the gatekeeper
  warning on first launch).
- Auto-update inside the Desktop app (no `electron-updater` channel
  yet; users re-download from the Releases page).
