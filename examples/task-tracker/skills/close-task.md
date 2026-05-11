---
name: close-task
description: >-
  Transition a task from `in_review` to `done`. Updates `status`,
  stamps `closed_at`, re-materializes so downstream `is_blocked`
  values flip to `false` for any task whose dependencies are now
  fully closed, and reports which tasks just became eligible.
audience: agent
arguments:
  - name: task_id
    description: The id of the task to close (e.g. APIV2-003).
    required: true
  - name: verification
    description: >-
      Comma-separated list of verification gates that passed (e.g.
      "pytest,drift-check,viewer-smoke"). Appended to the row's
      `verification` array. Pass "none" to keep the array unchanged.
    required: true
tools:
  - get_record
  - upsert_records
  - materialize
  - query
allowed_actors:
  - "agent:*"
  - "human:*"
---

# Close a task

Done is a write step plus a derivation refresh. The refresh is what
makes the tracker useful — downstream rows that were `is_blocked = true`
flip to `false` automatically.

## Steps

1. **Read the row first.** Confirm `status = 'in_review'`. If the
   row is already `done` or still `in_progress`, refuse and report
   back; closing requires `in_review`:
   ```bash
   folio get-record . {task_id}  # or: folio list . --filter "id = '{task_id}'"
   ```

2. **Compute the new `verification` array.** Take the existing list,
   append every gate from `{verification}` (skipping duplicates), and
   re-emit as JSON. If `{verification}` is `none`, keep the list
   unchanged.

3. **Upsert the closure.** One JSONL line; only the fields that
   change need to be sent (upsert merges with the existing row):
   ```bash
   folio upsert . --actor agent:close --file - <<JSONL
   {"id":"{task_id}","status":"done","verification":[...new array...],"closed_at":"<NOW ISO>","updated_at":"<NOW ISO>"}
   JSONL
   ```

4. **Re-materialize.** Every row that *transitively* depends on
   `{task_id}` will recompute `is_blocked`:
   ```bash
   folio materialize . --actor agent:close
   ```
   Materialize honours the input-hash cache, so only the affected
   rows re-run — the rest skip.

5. **Report what got unblocked.** Query the rows that were blocked
   before this run but are now eligible:
   ```bash
   folio query . "
     SELECT id, title, priority
       FROM records
      WHERE status = 'pending'
        AND is_blocked = false
        AND list_contains(CAST(depends AS VARCHAR[]), '{task_id}')
      ORDER BY priority_score DESC
   "
   ```
   Hand back the result as: "Closing `{task_id}` unblocked: …" or
   "Closing `{task_id}` did not unblock any downstream task."

## Notes

- The verification list is **append-only** in this skill. To replace
  the list (e.g. when a previously-passing gate is now failing), an
  explicit `mark-verified --remove` step would be needed; we keep
  things append-only here to match the project's broader
  audit-trail policy.
- The provenance line for `closed_at` is **not** written today —
  direct writes via `upsert_records` don't generate provenance
  entries (see SPECIFICATION.md §3.3.2). The git commit that follows
  the close is the durable audit anchor.
- If the agent realises mid-step that the task is *not* actually
  done (e.g. a verification gate failed), it must `upsert` a fresh
  row with `status: in_progress` and `notes` explaining why — never
  silently abandon mid-skill.
