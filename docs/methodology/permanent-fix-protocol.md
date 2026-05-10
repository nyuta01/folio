# Permanent Fix Protocol

The rule is simple: log repeated agent failures and prevent the next recurrence
with a deterministic guard whenever possible.

## What Counts As A Failure

Log a failure when agent work causes or nearly causes one of these outcomes:

- stale docs after behavior changes
- missing verification evidence
- over-broad scope or partially finished work
- inconsistent task state
- architectural boundary drift
- broken local setup or verification command
- security-sensitive behavior, such as unsafe filesystem path handling
- repeated mismatch against the contract.yaml, records.jsonl, derivation,
  provenance, or cache-key semantics defined in the design overview
- a sample sheet that breaks `tar`-portability by bundling caches, virtual
  environments, or environment-dependent state

Minor typo fixes do not need entries unless they repeat or hide a process gap.

## Required Loop

1. Add an entry to `docs/agent-failures.md`.
2. Use `observing` for the first non-critical occurrence.
3. If the class repeats, mark it `needs-fix`.
4. Link the entry to a task in `docs/exec-plans/feature-list.json`.
5. Link the entry to an active plan under `docs/exec-plans/active/`.
6. Implement the permanent fix in the smallest reliable place.
7. Prefer deterministic prevention:
   - `scripts/harness_check.py`
   - `scripts/harness_drift.py`
   - `scripts/validate_docs.py`
   - `make verify`
   - product specs
   - concise `AGENTS.md` rules
8. Run `make verify`.
9. Mark the failure entry `fixed` and record the permanent fix.

`needs-fix` entries always fail `make verify`, but the drift check still
requires them to link a task and plan. This keeps the loop restartable.

Security-sensitive failures and portability regressions may go directly to
`needs-fix`.

## Anti-Patterns

- Adding a long instruction when a script can enforce the rule.
- Marking a task done without verification evidence.
- Leaving active plans unreferenced from structured task state.
- Treating chat history as the source of truth.
- Letting `needs-fix` failures pass verification.
