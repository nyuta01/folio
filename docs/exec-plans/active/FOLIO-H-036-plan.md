# FOLIO-H-036 Plan: Enforce materialize field ACLs

## Goal

Close the authorization bypass where `Sheet.materialize()` could write a
derived value into a field protected by `x-editable-by` without checking
whether the materialize actor was allowed to edit that field.

## Scope

- `src/folio/sheet.py` — reuse the existing `_check_editable_by()` helper for
  every selected derivation target before any kind driver runs, records are
  mutated, or provenance is appended.
- `tests/test_materialize.py` — prove a denied actor cannot upsert or
  materialize a protected derived field, that records and provenance remain
  unchanged, and that an allowed actor can still materialize it.
- `scripts/harness_drift.py` — pin the materialize ACL call and regression test
  so future refactors cannot silently remove the authorization check.
- Specs, ADR-0007, public docs, and handoff artifacts — document materialize as
  a field write path subject to `x-editable-by`.

## Out of scope

- Redesigning actor strings, authentication, or role management.
- Adding derivation-specific ACLs separate from `x-editable-by`.
- Changing the materialize failure envelope for kind execution errors;
  permission failures remain `PermissionDeniedError`, matching direct upserts.

## Evidence

- `uv run pytest tests/test_materialize.py -q` passes.
- `python3 scripts/harness_drift.py` passes.
- `make verify` passes before this task is marked complete.

## Observation

`upsert_records()` required an actor and called `_check_editable_by()` before
mutating records. `materialize()` also required an actor but wrote
`records[position][target] = values[target]` and appended provenance without
checking the target field's `x-editable-by` allowlist. A non-matching actor
could therefore materialize an import, AI, or extension derivation into a
protected derived field that direct upsert would reject.

## Decision

Treat materialize as the field write path that it is. For each selected
derivation target, call `_check_editable_by({target: None}, effective_actor)`
before prompt loading, import loading, cache lookup, external kind execution,
record mutation, or provenance append. This preserves the existing ACL
semantics and fails before doing unnecessary side effects for unauthorized
materialization attempts.

## Permanent Fix

`tests/test_materialize.py::test_materialize_respects_target_editable_by_acl`
adds the regression: `guest` cannot upsert the protected target, cannot
materialize it, leaves `records.jsonl` unchanged, and appends no provenance;
`admin` can still materialize the same derivation. `scripts/harness_drift.py`
rejects removing the materialize ACL check or the regression test.

## Next Check

Any future records/provenance write path must add an `x-editable-by` regression
before it is exposed through SDK, CLI, Viewer, or automation surfaces.
