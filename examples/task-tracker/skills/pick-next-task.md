---
name: pick-next-task
description: >-
  Find the single best next task the agent should pick up: highest
  priority among `pending` rows whose `is_blocked` is false. Returns
  enough context (id, title, plan_url, paths, notes) for the agent to
  proceed without a second query.
audience: agent
arguments:
  - name: owner_filter
    description: >-
      Limit to tasks whose `owner` matches (e.g. "agent" or "shared").
      Pass "any" to ignore the filter.
    required: true
tools:
  - query
  - list_records
allowed_actors:
  - "agent:*"
  - "human:*"
---

# Pick the next task

The tracker only surfaces *one* task at a time. Picking next is a
read-only operation; the actual status update happens later in
`execute-task` / `close-task`.

## Steps

1. Make sure derivations are fresh — `is_blocked` reflects whether
   each task's dependencies are still open:
   ```bash
   folio materialize . --actor agent:pick
   ```

2. Query the unblocked pending queue, ordered by priority then age:
   ```bash
   folio query . "
     SELECT id, title, priority, owner, plan_url, dep_count,
            paths, notes
       FROM records
      WHERE status = 'pending'
        AND is_blocked = false
        $OWNER_PREDICATE$
      ORDER BY priority_score DESC, created_at ASC
      LIMIT 1
   "
   ```
   Where `$OWNER_PREDICATE$` is:
   - `AND owner IN ('agent','shared')` when `{owner_filter}` = `agent`
   - `AND owner = 'human'`                when `{owner_filter}` = `human`
   - empty                                when `{owner_filter}` = `any`

3. **If the query returns zero rows**, the next-best move is to
   clear something blocking. Run:
   ```bash
   folio query . "
     SELECT id, title, priority, dep_count
       FROM records
      WHERE status IN ('in_progress','in_review')
      ORDER BY priority_score DESC, updated_at ASC
   "
   ```
   and hand the result back as: "no unblocked pending work; the
   following items are mid-flight and unblock others when they close
   — pick one of these to push on, or wait."

4. **If the query returns one row**, hand it back as a single
   markdown block containing:
   - the id and title
   - whether a `plan_url` exists; if not, the next sub-step is
     [`plan-task`](plan-task.md)
   - the file paths the task is expected to touch
   - the notes block

## Notes

- This skill is read-only — no mutations, no provenance side-effects.
- The materialize call at step 1 is important: derivations are
  cached on `input_hash`, so if a dependency closed but you haven't
  re-materialized, `is_blocked` may be stale. Pass `--force` only if
  you suspect a clock-skew bug.
- The agent **must not** also change the task's `status` here. That
  belongs to `execute-task` (an explicit transition needs a
  paired `upsert` so the actor is captured).
