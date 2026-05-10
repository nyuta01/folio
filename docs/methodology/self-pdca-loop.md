# Self-PDCA Loop

The harness exists to make agent work self-improving. Every non-trivial change
should leave behind better instructions, checks, or evidence than it started
with.

## Loop Contract

| Phase | Input | Agent Action | Required Output |
|---|---|---|---|
| Plan | `feature-list.json`, active plans, quality score, design docs | Pick one bounded task, state acceptance criteria, identify verification gates | Active plan with scope and expected checks |
| Do | Active plan and repo context | Make the smallest coherent change | Code, docs, or scripts scoped to the task |
| Check | `make verify`, smoke tests, quality score, failure log | Run deterministic checks and inspect evidence | Verification result and observations recorded in the plan |
| Act | Check results and repeated failures | Convert lessons into permanent guardrails | Updated check, doc, task state, quality score, or failure log |

## Required Plan Sections

Every active plan, including completed plans kept in `docs/exec-plans/active/`,
must contain these sections:

- `## Observation`
- `## Decision`
- `## Permanent Fix`
- `## Next Check`

Use `N/A` only when there is truly no permanent fix or next check yet, and say
why. Do not leave the section empty.

## Failure Escalation

Failure entries in `docs/agent-failures.md` must link to a structured task and
an active plan before they can be fixed.

Required fields for a failure entry:

```markdown
## F-001 Short title

- **Status**: `observing`
- **Task**: `FOLIO-H-002`
- **Plan**: `docs/exec-plans/active/example-plan.md`

### Observation

What happened.

### Permanent fix

What changed to make recurrence less likely.
```

`needs-fix` entries intentionally fail `make verify`. They must still link a
task and plan so the next agent can continue without chat history.

## Quality Feedback

`docs/QUALITY_SCORE.md` is the lightweight retrospective artifact. Update it
when:

- a domain score changes
- a new weak spot appears
- verification coverage improves
- an implementation choice changes risk

Any domain scored `1` or `2` must name a next task in the `Next Task` column.
