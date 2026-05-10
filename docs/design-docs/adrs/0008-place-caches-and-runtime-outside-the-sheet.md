# ADR-0008 Place Caches and Runtime Outside the Sheet

- **Status**: `accepted`
- **Date**: `2026-05-10`
- **Decision makers**: `agent`
- **Related**: `docs/design-docs/overview.md` §5.4, §13

## Context

The whole point of a sheet being a portable data unit is that
`tar czf my-sheet.tgz my-sheet/` produces an archive whose size is
strictly proportional to the data, not the environment. The design
overview §13 already excludes computation caches, script-execution
environments (Python venv, Node `node_modules`), and audit logs from
the sheet directory and routes them to the user's cache directory.

Folio's reference implementation must make the right thing easy to do.
A future agent who reaches for `<sheet>/.folio-cache/` or
`<sheet>/.venv/` for convenience would silently re-introduce the
non-portable artifacts the spec exists to eliminate.

## Decision

Anything environment-dependent or rebuildable lives outside the sheet
directory:

- **Computation cache** (Phase 1+) goes under
  `<user-cache>/folio/<sheet-id>/cache/`. Examples:
  `~/.cache/folio/<sheet-id>/cache/` on Linux,
  `~/Library/Caches/folio/<sheet-id>/cache/` on macOS,
  `%LOCALAPPDATA%\folio\<sheet-id>\cache\` on Windows.
- **Script execution environment** (Phase 2+) goes under
  `<user-cache>/folio/<sheet-id>/runtime/`.
- **Audit logs** are exported externally as needed; they are not
  retained inside the sheet.
- **Repository-level virtual environment** (this project's `.venv`,
  managed by `uv`) lives at the **repository** root, not inside any
  sample sheet under `tests/`.

`<sheet-id>` resolves from the contract's `id` field. Cache-collision
handling for sheets that share the same `id` is an open issue tracked
in the design overview Appendix B (`sheet-id collision avoidance`).

## Consequences

- A `tar` of a sheet directory is reproducible across machines without
  including build artifacts that won't run on the target.
- Receivers of an archived sheet rebuild caches and venvs on first
  use. First-call latency is higher; subsequent calls hit the cache.
- The reference implementation must never write under `<sheet_path>`
  for transient state. The only files it writes inside a sheet are
  `records.jsonl`, `provenance.jsonl`, `.lock` (during writes), and
  the temp file used by atomic writes.
- The harness must keep sample sheets under `tests/` free of
  environment-dependent state.

## Confirmation

`tests/test_sheet.py::test_atomic_write_preserves_original_on_failure`
asserts that no `.records.*.jsonl.tmp` leftover remains in the sheet
directory after a failed write. The repo's `.gitignore` excludes
`.folio-cache/`, `.folio-runtime/`, and `.venv/` so an accidental commit
of any of them stays out of the harness baseline. Reviewers should
flag any code path that creates a path like `<sheet>/.cache/` or
`<sheet>/.venv/`. `make verify` runs the test under the
`python-test` gate.

## Alternatives Considered

- Place caches under `<sheet>/.cache/`. Convenient for single-machine
  use, but breaks `tar`-portability the moment a sheet is moved.
  Rejected.
- Introduce a sheet-local `cache/` with explicit `.gitignore` and
  `tar`-exclude guidance. Pushes the correctness burden to every user
  rather than enforcing it in the implementation. Rejected.
- Store caches under XDG `$STATE_HOME` instead of `$CACHE_HOME`. State
  data and cache data have different cleanup semantics; folio caches
  are rebuildable, so cache home is the right choice.
