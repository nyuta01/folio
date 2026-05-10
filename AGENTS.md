# Agent Instructions

This repository is built AI-first. Keep this file compact; it is the routing
layer into repo-local source-of-truth docs, not a full manual.

## Mission

Folio defines portable, AI-native data sheets. One sheet is one directory of
plain files (`contract.yaml`, `records.jsonl`, optional derivations,
provenance, scripts, attachments) that AI agents can read and write as
first-class users, that humans can review later, and that can be carried
across machines as a `tar` archive.

## Start Here

Read these in order before changing code:

1. `docs/design-docs/README.md` - canonical design docs and ADR index.
2. `docs/design-docs/overview.md` - complete product and technical design.
3. `docs/product-specs/phase-0-minimum-sheet.md` - first executable slice.
4. `docs/methodology/harness-engineering.md` - AI-first workflow.
5. `docs/methodology/self-pdca-loop.md` - agent self-improvement loop.
6. `docs/methodology/permanent-fix-protocol.md` - repeated failure handling.
7. `docs/QUALITY_SCORE.md` - current quality baseline and weak spots.
8. `docs/exec-plans/feature-list.json` - structured task state.
9. `docs/exec-plans/active/` - active implementation plans.
10. `AGENT_PROGRESS.md` - latest handoff state.

## Working Rules

- Work one bounded feature or plan at a time.
- Prefer boring, inspectable infrastructure that agents can reason about.
- Do not mark work done from code inspection alone; run the relevant checks.
- If behavior changes, update the matching product spec, design doc, or ADR.
- If an agent failure repeats, promote the fix into docs, scripts, or a
  deterministic check.
- Keep generated or derived material under `docs/generated/` when it appears.
- Sheet portability matters: do not place caches, virtual environments, or
  environment-dependent state inside a sample sheet directory.

## Verification

Use the harness entrypoint:

```bash
make agent-init
```

Before calling work done, run:

```bash
make verify
```

Today `make verify` runs the harness, drift, and docs gates. As implementation
lands, it must become the single gate for Python tests, CLI smokes, MCP smoke,
and Viewer smoke.

## Completion Rule

Before ending a task:

1. Update `docs/exec-plans/feature-list.json` for task state changes.
2. Update the active plan with Observation, Decision, Permanent Fix, and Next
   Check.
3. Update `docs/QUALITY_SCORE.md` when quality or risk changed.
4. Update `docs/agent-failures.md` when the task fixes or reveals a repeated
   agent failure.
5. Run `make verify`.
6. Leave `AGENT_PROGRESS.md` with restartable next steps if work is incomplete.
