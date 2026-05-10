# FOLIO-H-012 Plan: Sheet Materialize Loop, CLI Verbs, and Smoke

## Goal

Wire the Phase 1 building blocks (derivations, import kind, cache,
provenance, ai kind) into a single `Sheet.materialize()` loop, expose
the matching CLI verbs, and ship a deterministic smoke that walks the
§23.3 scenario without network access.

## Scope

- Extend `src/folio/derivation.py`:
  - `DerivationFile` dataclass holding `(derivation, path)`.
  - `load_derivation_files(sheet_path) -> list[DerivationFile]` so the
    materialize loop can compute `derivation_file_hash` from the source
    path.
- Extend `src/folio/_ai_kind.py`:
  - `resolve_prompt_body(sheet_path, derivation)` returning the prompt
    body whether it is inline (`prompt:`) or a `prompt_ref:` file under
    the sheet directory. The resolver enforces that `prompt_ref`
    targets stay under the sheet root (consistent with import sources).
- Extend `src/folio/sheet.py`:
  - `Sheet.materialize(targets=None, record_ids=None, force=False,
    actor=None, ai_client=None) -> {materialized, skipped, failures,
    total_cost}` per §10.6. The loop iterates derivation files in
    topological order, processes every target produced by each file
    once (so multi-target ai derivations cost a single API call),
    skips records whose latest provenance is `human_override` when
    `respect_human_override` is `True` and `force=False`, skips
    records whose `input_hash` matches the latest provenance, reads
    cached results before invoking the kind driver, persists records
    with `_records.atomic_write_records`, and appends provenance only
    after the records write succeeds (matches the design overview
    Appendix B note on materialize atomicity).
  - `Sheet.materialization_status(targets=None)` returning per-target
    counts (`total_records`, `with_provenance`, `ai_count`,
    `import_count`, `human_override_count`, `last_at`, `last_actor`).
    Stale-count is omitted because it requires a full input_hash
    sweep; it lands as a future enhancement.
  - `Sheet.provenance(record_id, field, history=False)` delegating to
    `_provenance.latest_provenance` / `field_history`.
  - Internal `_default_ai_client_factory()` so CLI tests can swap the
    default Anthropic adapter for `StubAIClient`.
- Extend `src/folio/cli.py`:
  - `folio materialize <sheet> [<field>] [--ids <list>] [--force]
    --actor <a>` printing the §10.6 envelope as JSON.
  - `folio status <sheet> [<field>]` printing the materialization
    status JSON.
  - `folio provenance <sheet> <record_id> <field> [--history]`.
- New tests:
  - `tests/test_materialize.py` covering: ai materialize with
    `StubAIClient`, multi-target ai materialize (single API call),
    import materialize from CSV, dependency-ordered materialize where
    `b` derives from `a`, cache hit on second invocation, force
    bypassing both stale and `human_override` checks, missing-record
    failure entry, ai-failure surfacing as a `failures` entry rather
    than raising, status counts per source, and provenance latest +
    history reads.
  - `tests/test_cli.py` extensions covering each new verb.
- `scripts/smoke-materialize.sh` invoking
  `scripts/_materialize_smoke.py`. The Python harness builds a temp
  sheet, materializes via the SDK with `StubAIClient`, and asserts
  the §23.3 scenario end-to-end (validate, count nulls, materialize,
  distribution, human override, provenance history).
- `scripts/harness_check.py` requires the new modules, tests, smoke
  script, smoke harness, and the `materialize-smoke` line in the
  verify target.
- `Makefile` adds `materialize-smoke` and includes it in `verify`.

## Out of scope

- Stale-count in `materialization_status`. Tracked as a future
  enhancement.
- TOON output for materialize / status / provenance verbs. Phase 3.
- Live network smoke. ADR-0009 rules out network access from
  `make verify`.

## Evidence

- `make verify` passes locally with the expanded `python-test`,
  `cli-smoke`, and the new `materialize-smoke`.
- `scripts/_materialize_smoke.py` exits 0 against a freshly built
  temp sheet without a live API key.

## Observation

`FOLIO-H-009` … `FOLIO-H-011` provide every Phase 1 building block:
typed derivations, import-kind execution, cache key + cache
filesystem, provenance log, and the ai-kind driver behind a Protocol.
They are not yet wired into `Sheet`, so the existing CLI (`validate`,
`query`, `list`, `count`, `upsert`, `delete`) cannot honor derived
fields, materialize records, or surface lineage. A user running the
Phase 0 CLI today on a Phase 1 sheet would silently bypass
derivations.

## Decision

- Iterate over derivation **files** (not targets) so a multi-target
  ai derivation costs one API call. Targets that share a derivation
  instance update together; the cache hit path treats the whole
  result as a single unit.
- Append provenance entries only after the records.jsonl atomic
  write succeeds. If the records write fails, the provenance log
  stays consistent with what is on disk; if a provenance append
  fails after the records write, the user can re-run materialize
  (the records change is observable and the cache will let
  subsequent calls short-circuit).
- Surface kind-execution failures as `failures` entries on the
  return value. Raising would abort the loop, which makes large
  materializations harder to reason about.
- Keep materialize-smoke as a Python harness invoked from bash, so
  stub setup stays in the test layer (consistent with ADR-0009).

## Permanent Fix

- `make verify` now runs `materialize-smoke`. Removing the smoke
  script, harness, or its CLI verbs fails the gate.
- `scripts/harness_check.py` requires the new modules, tests, smoke
  files, and the `materialize-smoke` Makefile line.
- The dependency-order test pins the topological-sort behavior at
  the materialize boundary.

## Next Check

Phase 1 is complete after this task. Future enhancements:

- Add stale-count to `materialization_status` (requires a full
  `input_hash` sweep; reopen when the ai kind sees production use).
- Consider promoting a semantic ADR-to-code drift check that
  asserts `anthropic` is imported only in `AnthropicClientAdapter`
  (`FOLIO-H-006` standing scope).
