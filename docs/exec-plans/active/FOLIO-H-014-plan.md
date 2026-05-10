# FOLIO-H-014 Plan: scripts/ Runtime

## Goal

Land the reusable `scripts/` surface so humans and (later, in
Phase 4) the `python` derivation kind can invoke a sheet-local
helper without bundling environment state inside the sheet itself.

## Scope

- `src/folio/scripts.py`:
  - `discover_scripts(sheet_path) -> dict[name, Path]` walking
    `<sheet>/scripts/`. Ignores subdirectories and unsupported
    extensions; raises on duplicate basenames.
  - `runtime_root_for_sheet(sheet_id) -> Path` resolving
    `<user-cache>/folio/<sheet-id>/runtime/` via `platformdirs`,
    matching ADR-0008.
  - `run_script(sheet_path, sheet_id, name, args=None,
    timeout_seconds=60) -> ScriptResult` rejecting name traversal,
    dispatching to a Python or shell runner, and returning
    `ScriptResult(exit_code, stdout, stderr, duration_seconds)`.
  - Python runner uses `sys.executable` when no
    `scripts/requirements.txt` is present and creates a venv at
    `<runtime>/python/.venv/` only when requirements are declared.
  - Shell runner uses `/bin/bash` (the system `bash`).
  - Both runners pass the sheet path as the first script argument
    so scripts can resolve `records.jsonl` / `contract.yaml` without
    extra setup.
- `Sheet.run_script(name, args=None, timeout_seconds=60)` delegating
  to the helper.
- `folio script run <sheet> <name> [args...]` and `folio script list
  <sheet>` CLI sub-commands under a Typer sub-app.
- `tests/test_scripts.py` covering: discovery (empty / single .py /
  shared name + suffix), name-traversal rejection, Python execution
  with the sheet path as `argv[1]`, shell execution, timeout
  surfacing as `ScriptError`, and `runtime_root_for_sheet`
  placement (mocked).
- `scripts/smoke-scripts.sh` building a temp sheet with a `.py` and
  a `.sh` script and asserting the CLI output.
- `Makefile` adds `scripts-smoke` and includes it in `verify`.
- `scripts/harness_check.py` requires the new module, the new test,
  the new smoke script, and the matching verify-target line.

## Out of scope

- The `python` derivation kind that *calls* a function in a script.
  `FOLIO-H-021` (Phase 4).
- Node.js script execution. The discovery layer recognizes `.js` as
  unsupported but execution is deferred.
- Long-running script policies (per-script timeout, sandboxing).
  The fixed 60-second default is enough for Phase 2.
- Capturing script-side provenance entries. Scripts are utilities,
  not derivations.

## Evidence

- `make verify` passes locally with the new `python-test` cases and
  the new `scripts-smoke`.
- A Python script invoked via the CLI sees the sheet path as
  `sys.argv[1]`.

## Observation

The Phase 2 spec (`docs/product-specs/phase-2-scripts-and-readme-frontmatter.md`)
commits to `scripts/` execution but no code exists yet, and ADR-0008
forbids placing runtime state inside the sheet. Without this task,
`FOLIO-H-021` (the Phase 4 `python` kind) cannot start.

## Decision

- Use the system Python (`sys.executable`) by default and only
  create a venv when `scripts/requirements.txt` is declared. Most
  Phase 2 use cases will not need extra dependencies, so the
  no-venv path keeps the smoke fast and offline.
- Pass the sheet path as the first script argument so callers do
  not have to rediscover it via environment variables.
- Reject script names that contain anything outside
  `[a-zA-Z0-9_-]` to prevent path traversal at the API boundary;
  discovery still uses `iterdir()` so file-system aliasing tricks
  cannot smuggle names past the regex.

## Permanent Fix

- `scripts/harness_check.py` requires `src/folio/scripts.py`,
  `tests/test_scripts.py`, `scripts/smoke-scripts.sh`, and the
  `scripts-smoke` line in the verify target.
- `make verify` now runs the new smoke, so a regression that
  removes the script-runner surface fails the gate.
- The path-traversal test pins the safe-name invariant.

## Next Check

`FOLIO-H-015` adds the README YAML frontmatter (`Sheet.metadata`).
`FOLIO-H-021` (Phase 4) consumes `Sheet.run_script` from the
`python` derivation kind once the kind registry from `FOLIO-H-020`
exists.
