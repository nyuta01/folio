# ADR-0006 Use a Single-Writer .lock for Sheet Writes

- **Status**: `accepted`
- **Date**: `2026-05-10`
- **Decision makers**: `agent`
- **Related**: `docs/design-docs/overview.md` §12

## Context

Multiple AI agents and humans may operate the same sheet directory
concurrently. The design overview §12 chooses a single-writer model with
a `.lock` file under the sheet, atomic temp file + rename writes for
rewritten sheet files, and OS-level atomic appends for `provenance.jsonl`.
CRDT is explicitly rejected.

Without an ADR, a future agent could legitimately try to introduce
optimistic concurrency, multi-writer merging, or a heavier coordination
service. Pinning the decision keeps the data layer simple and
auditable.

## Decision

Writes to a sheet acquire `<sheet_path>/.lock` via the `filelock` library
with a default timeout of 30 seconds. Reads do not acquire the lock and
may run concurrently. After the write completes (or fails), the `.lock`
file is removed. `records.jsonl` updates and SDK-driven `contract.yaml`
updates use exclusive random same-directory temp files + `os.replace` so a
partial write cannot replace the canonical file and attacker-created
predictable temp symlinks are not followed.

Concurrent writes from multiple agents must be serialized by an upstream
queue or by retrying after lock acquisition. CRDT-based collaborative
editing is out of scope (§14.3).

## Consequences

- The data layer is reasoning-friendly: a writer either holds the lock
  or it doesn't, and a successful `os.replace` is an atomic transition.
- Lock contention is naturally bounded by the 30-second timeout.
  Long-running writers must release explicitly before the timeout
  expires.
- Two writers in different processes interleave correctly, but the
  loser sees its records merged with the winner's view at the next
  acquisition. Higher-level coordination (queues, work-stealing) is the
  caller's responsibility.
- The lock file on Windows uses a different acquisition primitive than
  on POSIX, but `filelock` papers over the difference.

## Confirmation

`tests/test_sheet.py::test_lock_serializes_concurrent_writers` runs two
threads through a `threading.Barrier` and asserts that both writes
land. `test_atomic_write_preserves_original_on_failure` patches
`os.replace` to fail and asserts the original `records.jsonl` is
untouched and no `*.tmp` leftover remains.
`tests/test_contract.py::test_contract_write_ignores_predictable_tmp_symlink`
pre-creates `contract.yaml.tmp` as a symlink and asserts schema edits do not
clobber the symlink target. Both run under `make verify`.

## Alternatives Considered

- File system-level POSIX advisory locks via `fcntl`. Smaller dependency
  surface, but worse Windows portability. Rejected; `filelock` already
  handles the cross-platform path.
- Optimistic concurrency with version stamps in records. Better for
  many-writer fan-in, but adds visible state to `records.jsonl` and
  conflicts with the simplicity-first priority. Rejected.
- CRDT-based collaborative editing. Out of scope per §14.3.
