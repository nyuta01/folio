---
purpose: Engineering task tracker for AI-agent-driven feature work — captures the backlog, surfaces unblocked next work, propagates dependency closures, and reports a standup digest.
default_actor: agent:human:you
tags: [tasks, backlog, agent-loop, dependency-graph, cli-driven]
agent_skills: [pick-next-task, close-task, daily-standup]
---

# task-tracker

**The use case:** you (a tech lead, PM, or solo developer) have a
backlog of well-scoped engineering tasks. You want to delegate the
execution to AI coding agents (Claude Code, Cursor, Codex, …) and
spend your own time only on the parts that actually need human
judgment — prioritisation, dependency calls, and review. You need a
backlog that's structured enough for an agent to operate on
autonomously *and* simple enough that you can read it directly in
your editor.

This sheet is built specifically for that loop. It's modelled on
the project's own
[`docs/exec-plans/feature-list.json`](../../docs/exec-plans/feature-list.json) —
the same shape Folio's maintainers use to coordinate their own
agent work. Use it as a starting point for your own backlog; the
shape generalises.

## What you get over a plain JSON backlog

| Pain point | What this sheet does |
|---|---|
| "Which task is next, given the dependency graph?" | `is_blocked` is a derivation. When you close a task and re-materialize, every downstream row recomputes — the agent immediately sees what just became eligible. |
| "Did this task land with proper verification?" | `verification_count` rolls up the list of gates that passed. Standups query `status='done' AND verification_count=0` to find quietly-merged work. |
| "Who's working on what right now?" | `daily-standup` skill produces the digest from a handful of SQL queries — no manual rollup, no Notion sync. |
| "How big is this task really?" | `path_count` and `dep_count` are cheap proxies for size and risk. Sortable. Comparable across rows. |
| "Can an AI agent actually drive this end-to-end?" | Three packaged skills (`pick-next-task`, `close-task`, `daily-standup`) walk the loop step-by-step. The agent uses its built-in Bash tool to run `folio` CLI verbs — no MCP server required. |

The sheet is **git-versioned**. Every status change is one diff,
visible in `git log -p records.jsonl`. That's the durable audit
trail; provenance covers the derivation side.

## The loop

```text
                       ┌─────────────────┐
                       │ AI coding agent │
                       │   uses Bash to  │
                       │   call `folio`  │
                       └────────┬────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
   1. pick-next-task   2. <do the work>     3. close-task
   ──────────────────  ─────────────────    ──────────────────
   `folio materialize` agent edits code     `folio upsert`
   `folio query …`     in the repo, runs    sets status=done
   → picks 1 row       tests / gates        `folio materialize`
                                            → downstream rows
                                              recompute `is_blocked`
                                              and become eligible
                                │
                                ▼
                       ┌─────────────────┐
                       │  4. (anytime)   │
                       │  daily-standup  │
                       │  → markdown     │
                       │  digest for     │
                       │  the human      │
                       └─────────────────┘
```

Steps 1, 3, and 4 are packaged as skills the agent follows literally.
Step 2 is the actual engineering work the agent does in the rest of
your repo — Folio doesn't touch that; it just records the state
transitions around it.

## Try it

```bash
# 1. Validate + materialize the seed.
folio validate examples/task-tracker
folio materialize examples/task-tracker --actor agent:demo

# 2. What's ready to pick up?
folio query examples/task-tracker "
  SELECT id, priority, title
    FROM records
   WHERE status = 'pending'
     AND is_blocked = false
   ORDER BY priority_score DESC, created_at ASC
"
# → only APIV2-006 — its single dep (APIV2-002) is already done.

# 3. What's mid-flight?
folio query examples/task-tracker "
  SELECT id, status, priority, assignee, title
    FROM records
   WHERE status IN ('planning','in_progress','in_review')
   ORDER BY priority_score DESC
"
# → APIV2-003 (in_review, P0), APIV2-004 (in_progress, P0), APIV2-007 (in_progress, P1), BILL-021.

# 4. Simulate: close APIV2-003 and watch the dependency graph propagate.
echo '{"id":"APIV2-003","status":"done","verification":["pytest","contract-tests","code-review"],"closed_at":"2026-05-11T12:00:00Z","updated_at":"2026-05-11T12:00:00Z"}' \
  | folio upsert examples/task-tracker --file - --actor agent:close
folio materialize examples/task-tracker --actor agent:close

# 5. Re-query — APIV2-008 was blocked on (003, 004); 003 is now done, but 004 is still in_progress, so 008 stays blocked. APIV2-005 was blocked on 003 alone → now its `is_blocked` flipped to false.
folio query examples/task-tracker "
  SELECT id, status, is_blocked, title
    FROM records
   WHERE id IN ('APIV2-005','APIV2-008','APIV2-010')
"
```

The dependency propagation in step 5 is the load-bearing demo: a
single close + materialize updates every transitive blocker without
you having to update each row by hand.

## The schema in one glance

| Field | Type | Set by | Notes |
|---|---|---|---|
| `id` | string (PK) | author | `<EPIC>-NNN` convention |
| `title` | string | author | One-line summary |
| `epic` | string | author | Coarse grouping for rollups |
| `status` | string | workflow | `pending` / `planning` / `in_progress` / `blocked` / `in_review` / `done` / `cancelled` |
| `priority` | string | author | `P0` / `P1` / `P2` / `P3` |
| `owner` | string | author | `agent` / `human` / `shared` |
| `assignee` | string | workflow | Actor that picks the work up |
| `depends` | array | author | Other task ids that must reach `done` first |
| `plan_url` | string | planning step | Repo path or URL to the per-task plan |
| `paths` | array | planning step | Files the task will touch |
| `verification` | array | execution | Gates that have passed |
| `notes` | string | anyone | Free-form |
| `effort_estimate_hours` | number | planning | Cheap capacity proxy |
| `created_at` / `updated_at` / `closed_at` | timestamp | workflow | ISO-8601 |
| `priority_score` | int | python deriv. | `P0`→100 / `P1`→10 / `P2`→1 / `P3`→0 |
| `dep_count` | int | python deriv. | `len(depends)` |
| `path_count` | int | python deriv. | `len(paths)` |
| `verification_count` | int | python deriv. | `len(verification)` |
| `is_blocked` | bool | **sql deriv.** | True when any `depends` row is not yet `done`. Runs against the *whole sheet*, so it propagates on every materialize. |

Editable rules are intentionally **open by default** so any agent
actor can use the example out of the box. Tighten the
`x-editable-by` patterns on your own sheets once you know which
actors should own which fields.

## Skills

| Skill | Audience | What it does |
|---|---|---|
| [`pick-next-task`](skills/pick-next-task.md) | agent | Read-only — find the single best next task (highest priority, unblocked). |
| [`close-task`](skills/close-task.md) | agent | Transition `in_review → done`, append verification gates, re-materialize, report downstream unblocks. |
| [`daily-standup`](skills/daily-standup.md) | agent | Generate a five-section markdown digest of in-flight / ready / blocked / under-gated / epic rollups. Read-only. |

Discover them via `folio skill list examples/task-tracker`.

## Why this design vs. GitHub Issues / Linear / Jira

You'll outgrow this sheet around the point where a project tracker
needs SSO, multi-user comments, attachments, mobile UI, and SLA
automation. That's not what this is for. This is for the *first
six months* of a project — when:

- the backlog fits in a single editor window
- the contributors are 1-3 humans plus 1-N coding agents
- you want the audit log to live in the same git history as the
  code, not in a separate SaaS
- you want the agent to query and update the backlog as part of its
  normal Bash-tool repertoire, without an API token to manage

When the project outgrows this, `folio export datapackage` produces
a Frictionless Data Package you can import into a "real" tracker.

## Honest limitations

- `is_blocked` is recomputed at `folio materialize` time — it's not
  reactive to writes the way a database trigger would be. The
  `close-task` skill always pairs the upsert with an immediate
  materialize, which is enough in practice. If you want a tighter
  loop, you can wire a git pre-commit hook to run
  `folio materialize` automatically.
- Direct writes (`folio upsert` / `folio delete`) do **not** append
  `provenance.jsonl` entries today (see
  [SPECIFICATION.md §3.3.2](../../SPECIFICATION.md#332-when-provenance-is-written)).
  Status changes audit through git history. Derivation outputs
  (the five computed fields) *do* generate provenance lines, so the
  audit half of the loop applies to the "agent enriched this row"
  story but not to the "agent changed this row's status" story.
- Effort estimates and actuals are author-supplied; nothing here
  detects effort overruns automatically. Treat them as planning
  signals, not metrics.

## See also

- [`docs/exec-plans/feature-list.json`](../../docs/exec-plans/feature-list.json) — the project's own task list, in the same shape this example models.
- [AI agent operates, human verifies](https://nyuta01.github.io/folio/guides/agent-operated-sheet/) — the end-to-end agent-loop guide this example backs.
- [`folio-agent-skills`](https://www.npmjs.com/package/folio-agent-skills) — the product-knowledge skill pack the agent reads alongside these per-sheet skills.
