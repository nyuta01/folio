---
name: triage-candidates
description: Walk the candidate-status entries in research-memory and
             promote them to verified, demote them to rejected, or
             leave them as candidate with a follow-up note.
audience: agent
arguments:
  - name: max_records
    description: Cap how many candidates to triage in one pass.
    required: true
tools:
  - list_records
  - upsert_records
  - provenance
---

# Triage research candidates

Pull at most {max_records} candidates and decide what to do with
each. Goal: never let an unreviewed citation linger in the memory
for more than a week.

## Steps

1. Pull the queue (newest first):
   ```bash
   folio query . "
     SELECT id, query, title, url, domain
     FROM records
     WHERE status = 'candidate'
     ORDER BY id DESC
     LIMIT {max_records}
   "
   ```
2. For each row, decide:
   - **Verify**: the citation answers the original `query` and the
     `domain` is authoritative. `status: verified`, add a one-line
     `notes` field describing why.
   - **Reject**: the citation is off-topic or unreliable.
     `status: rejected`, `notes:` the reason.
   - **Hold**: needs deeper reading. Leave `status: candidate` and
     add a `notes: "review by <date>"` so the next triage knows.
3. Upsert the updates in one batch:
   ```bash
   folio upsert . --actor agent:research-triage --file - <<'JSONL'
   {"id":"f_001","status":"verified","notes":"IEA primary source."}
   {"id":"f_003","status":"rejected","notes":"Press release, not data."}
   JSONL
   ```
4. Skim `folio provenance . <id> status` afterwards — every change
   should carry your actor and a timestamp.

## Notes

- The `query` field tells you what the candidate was searching for;
  triage decisions should stay loyal to that original intent.
- Verified entries become input to higher-level summaries; rejected
  ones still stay in the sheet so a future triage doesn't redo the
  same work.
