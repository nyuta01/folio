# Harness Engineering

This repository follows an AI-first operating model. The harness is the
repository-local environment that lets coding agents do reliable work: compact
instructions, source-of-truth docs, structured task state, verification scripts,
architecture checks, failure logs, and handoff memory.

The goal is not to make a large process. The goal is to make the next agent run
restartable, bounded, and mechanically verifiable.

## Principles

### Small Agent Entry Point

`AGENTS.md` must stay short. It routes agents to the current source of truth
instead of duplicating the design.

Primary references:

- `docs/design-docs/README.md`
- `docs/design-docs/overview.md`
- `docs/design-docs/adrs/README.md`
- `docs/methodology/self-pdca-loop.md`
- `docs/QUALITY_SCORE.md`
- `docs/product-specs/phase-0-minimum-sheet.md`
- `docs/exec-plans/feature-list.json`
- `docs/exec-plans/active/`
- `docs/agent-failures.md`

### Repository As System Of Record

Decisions that matter to future agents belong in the repository. Do not rely on
chat history, memory, or external notes for product behavior, architecture
constraints, or verification expectations.

### Structured Task State

Task state lives in `docs/exec-plans/feature-list.json`. Each task has a stable
id, priority, status, affected paths, dependencies, plan URL, verification gates,
and notes.

### One Task At A Time

Agents should pick one highest-priority non-done task, complete it, verify it,
and update task state before expanding scope.

### Shift Feedback Left

`make verify` is the single repository gate. It starts with harness, drift,
and docs checks. As product code appears, add Python unit tests, CLI smoke,
and Viewer smoke behind the same target.

### CI Runs The Same Gate

GitHub Actions runs `make verify` on pull requests and pushes to `main`. CI must
not grow a second checklist of product checks; it prepares the runtime
toolchain and invokes the same Make target agents run locally.

### Permanent Fixes

If a mistake repeats, do not rely on "be careful next time." Record it in
`docs/agent-failures.md` and prevent the next occurrence with the smallest
reliable guard: a script, linter, product spec update, or AGENTS rule.

### Self-PDCA

Every non-trivial task follows the loop in
`docs/methodology/self-pdca-loop.md`: plan one bounded task, make the change,
check it with deterministic evidence, then act by updating a guardrail, quality
score, task state, or failure log.

### Sheet Portability Is A Harness Constraint

Folio's design treats `tar`-portability as a primary product invariant. The
harness must keep that invariant easy to honor: caches, virtual environments,
and audit logs live outside any sample sheet directory under
`docs/product-specs/` or in tests, and `make verify` should reject sample
sheets that bundle environment-dependent state.

## Current Verification Gates

| Gate | Command | Purpose |
|---|---|---|
| `ci_verify` | GitHub Actions `make verify` | Enforces the repository gate on pull requests and `main` pushes |
| `harness_check` | `make harness-check` | Validates required harness files and feature-list shape |
| `drift_check` | `make drift-check` | Validates active plan references and failure-log status |
| `validate_docs` | `make validate-docs` | Validates design-doc, ADR, and docs-local link structure |

## Target Harness Growth

As product code lands, `make verify` must add deterministic checks for:

- Pydantic v2 contract.yaml validation (Phase 0).
- DuckDB-backed read operations against `records.jsonl` (Phase 0).
- `folio` CLI smoke against a temporary local sheet (Phase 0).
- Derivation execution and provenance append-only behavior (Phase 1).
- Viewer smoke that starts the FastAPI server and exercises the read path
  (Phase 5).

Each Phase preserves the language-independent specification in
`docs/design-docs/overview.md`. Implementation choices that bind future agents
must be recorded as ADRs.
