# FOLIO-H-010 Plan: input_hash, Cache, and provenance.jsonl

## Goal

Land the cache key, the cache filesystem layer, and the
`provenance.jsonl` helpers so the ai-kind driver (`FOLIO-H-011`) and
the CLI verbs (`FOLIO-H-012`) can detect stale records and read /
write lineage without re-deriving the §11 / §9 contract.

## Scope

- `src/folio/_cache.py`:
  - `compute_input_hash(derivation, *, derivation_file_hash, inputs,
    prompt_body=None, source_file_hash=None) -> str` per §11. Output
    is `"sha256:" + hex` digest computed over a RFC 8785 canonical
    JSON payload.
  - `sha256_hex(bytes)` and `sha256_file(path)` helpers.
  - `default_cache_root(sheet_id) -> Path` resolving
    `<user-cache>/folio/<sheet-id>/cache/` via `platformdirs` (per
    ADR-0008).
  - `cache_path(cache_root, input_hash) -> Path`,
    `read_cache(cache_root, input_hash) -> dict | None`, and
    `write_cache(cache_root, input_hash, value) -> None`. Cache files
    use a two-character shard prefix to avoid huge directories.
- `src/folio/_provenance.py`:
  - `provenance_path(sheet_path) -> Path`.
  - `append_provenance(sheet_path, entry)` validates §9.1 required
    fields (`record_id`, `field`, `source`, `actor`, `at`) and
    appends a JSON line. Writes use `O_APPEND` to honor §12's atomic-
    append guarantee for entries within `PIPE_BUF`.
  - `read_provenance(sheet_path) -> list[dict]` parses the full log.
  - `latest_provenance(sheet_path, record_id, field) -> dict | None`
    returns the most recent entry per §9.1.
  - `field_history(sheet_path, record_id, field) -> list[dict]`
    returns the entire append-only history in order.
  - `is_stale(latest_entry, current_input_hash) -> bool`.
- `pyproject.toml` adds `rfc8785` and `platformdirs` to runtime
  dependencies.
- `tests/test_cache.py` covers: deterministic hashing across key
  reorderings (RFC 8785 stability), drift across edits to the
  derivation file hash / prompt body / model id / input value,
  ai-kind required arguments, import-kind required arguments, cache
  miss / hit / shard layout, and `default_cache_root` placement
  outside the sheet.
- `tests/test_provenance.py` covers: missing-file empty read, append
  + latest-wins read across two writes for the same `(record_id,
  field)`, history ordering, `human_override` resolution, malformed
  line rejection, and the `is_stale` truth table (no entry, equal
  hash, different hash).
- `scripts/harness_check.py` requires the new modules and tests.

## Out of scope

- Wiring cache hits / misses into a `materialize` operation. That is
  the job of `FOLIO-H-011`.
- Anthropic SDK integration. `FOLIO-H-011`.
- CLI verbs. `FOLIO-H-012`.
- An ADR pinning the cache layout shard scheme. Reopen if the layout
  changes between phases.

## Evidence

- `make verify` passes locally with the expanded `python-test`.
- Two consecutive `compute_input_hash` calls with rearranged input
  keys return the same digest (RFC 8785 stability).
- `latest_provenance` reflects the most recent entry after multiple
  appends.

## Observation

`FOLIO-H-009` provides the typed object graph for derivations but
gives the materialize loop nothing to compare or persist. Without a
deterministic `input_hash` and a provenance log, the ai-kind driver
cannot decide whether to call the model, and the CLI cannot answer
"who wrote this field, when, and from what?".

## Decision

- Use the `rfc8785` package (named in §11 of the design overview) so
  the canonical JSON encoder is the same one external consumers can
  reproduce without porting Folio code.
- Use `platformdirs.user_cache_dir("folio")` so the cache root
  matches §13.2 across Linux, macOS, and Windows without a
  custom platform shim.
- Hash bytes are emitted with the `sha256:` prefix that matches the
  example `provenance.jsonl` schema in §9.1.
- Provenance writes go through `O_APPEND` to honor the atomic-append
  guarantee in §12. Latest-wins resolution scans the file from the
  tail; for Phase 1 the log is small enough that a full read is
  acceptable.
- The cache directory uses a two-character shard prefix
  (`cache_root/<digest[:2]>/<digest>.json`) so the cache stays usable
  on filesystems that perform poorly with very large flat directories.

## Permanent Fix

- `scripts/harness_check.py` requires `src/folio/_cache.py`,
  `src/folio/_provenance.py`, and the matching test files. Removing
  any of them fails `make verify`.
- The deterministic hash test pins the RFC 8785 contract: a future
  change that swaps the canonical encoder for an order-sensitive one
  fails the gate.
- The provenance latest-wins test pins the §9.1 read semantics.

## Next Check

`FOLIO-H-011` introduces the ai kind. It must thread the cache and
provenance helpers into a materialize loop, deal with the Anthropic
SDK, and ship a deterministic stub mode so `make verify` keeps
running offline.
