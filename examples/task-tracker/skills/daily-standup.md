---
name: daily-standup
description: >-
  Generate the human-facing standup digest - what's mid-flight, what's
  ready to pick up, what's blocked and on whom, and which closed tasks
  shipped under-gated. Read-only.
audience: agent
arguments: []
tools:
  - query
  - list_records
allowed_actors:
  - "agent:*"
  - "human:*"
---

# Daily standup digest

A markdown digest the human (PM, tech lead, you) skims in 90 seconds
before opening the editor. Read-only — no mutations.

## Steps

1. **In flight** (every active task, ordered by priority):
   ```bash
   folio query . "
     SELECT id, epic, status, priority, assignee, title
       FROM records
      WHERE status IN ('planning','in_progress','in_review')
      ORDER BY priority_score DESC, updated_at ASC
   "
   ```

2. **Ready to pick up** (unblocked, pending):
   ```bash
   folio query . "
     SELECT id, epic, priority, owner, title, dep_count
       FROM records
      WHERE status = 'pending'
        AND is_blocked = false
      ORDER BY priority_score DESC, created_at ASC
   "
   ```

3. **Blocked and on whom**:
   ```bash
   folio query . "
     SELECT id, title, priority, depends
       FROM records
      WHERE is_blocked = true
        AND status NOT IN ('done','cancelled')
      ORDER BY priority_score DESC
   "
   ```
   For each blocked row, follow up with one targeted query per
   open dependency to surface *who* is the blocker:
   ```bash
   folio query . "
     SELECT id, status, assignee, updated_at
       FROM records
      WHERE id = '<dep-id>'
   "
   ```

4. **Under-gated closures** (red flag — landed without verification):
   ```bash
   folio query . "
     SELECT id, title, closed_at
       FROM records
      WHERE status = 'done'
        AND verification_count = 0
      ORDER BY closed_at DESC
      LIMIT 10
   "
   ```

5. **Epic rollups**:
   ```bash
   folio query . "
     SELECT epic,
            SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done,
            SUM(CASE WHEN status IN ('pending','blocked') THEN 1 ELSE 0 END) AS not_started,
            SUM(CASE WHEN status IN ('planning','in_progress','in_review') THEN 1 ELSE 0 END) AS in_flight,
            COUNT(*) AS total
       FROM records
      GROUP BY epic
      ORDER BY epic
   "
   ```

6. **Assemble.** Render the digest as one markdown document with
   five sections matching the five queries. Lead with the epic
   rollups — the human's first question is always "where are we
   overall?". Then the in-flight list, the ready queue, the blocked
   list (with blocker citations), and finally the under-gated
   closures.

## Notes

- The agent should be **conservative** about what it surfaces -
  don't list every blocked task if there are 30 of them; cap at the
  top 10 by priority.
- If the agent has a `chat` / `summarise` tool, it can replace the
  raw query output with one-sentence summaries; otherwise keep the
  table form so the human can spot anomalies (e.g. a P0 stuck in
  in_progress for two weeks).
- This skill is the canonical "what's the agent seeing?" view -
  running it once a morning is the cheapest way to keep the human
  in the loop.
