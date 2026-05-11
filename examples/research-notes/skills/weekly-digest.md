---
name: weekly-digest
description: Produce a Friday digest of this week's research notes
             grouped by category, with a one-line summary per note.
audience: agent
arguments:
  - name: since
    description: Cut-off date in ISO format (only include notes
                  authored on or after this date).
    required: true
tools:
  - query
  - list_records
---

# Weekly research digest (since {since})

Build a Friday roll-up of every note dated on or after {since},
grouped by `category`, so the team has a single artifact to skim
before the weekly review.

## Steps

1. Pull the notes:
   ```bash
   folio query . "
     SELECT id, category, title, body, word_count
     FROM records
     -- if your sheet doesn't track created_at, fall back to a
     -- per-category limit
     ORDER BY category, id
   "
   ```
2. Group by `category`. For each:
   - Heading: the category name in plain English.
   - For each note: one-line title + a 30-word summary distilled
     from `body` (LLM call OK if your runtime has one).
3. Emit the digest as markdown to stdout — let the caller decide
   where to ship it (Slack channel, email, an issue).

## Notes

- `word_count` is `x-derived` via a Python script; if a row has
  `word_count: null` it means materialize hasn't caught up — run
  `folio materialize . word_count --actor agent:digest` first.
- Keep summaries factual. The digest should be skimmable in 60
  seconds; opinions belong in the linked notes, not the roll-up.
