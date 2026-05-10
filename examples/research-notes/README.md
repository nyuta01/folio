# research-notes — Use Case 2.3: Semi-structured Research Data

Internal research notes — competitive analysis, technical
experiments, interview summaries — accumulated as one row per note.

| Field | Owner | Notes |
|---|---|---|
| `title`, `body` | `agent:human` | The note itself. |
| `category` | `agent:human` | `competitive` / `technical` / `market` / `internal`. |
| `tags` | `agent:human` | Free-form array. |
| `word_count` | derived (`python`) | Counted from `body` offline. |

## Try it

```bash
uv run folio validate examples/research-notes
uv run folio materialize examples/research-notes --actor agent:demo

# Slice by category
uv run folio query examples/research-notes \
  "SELECT category, COUNT(*) AS n, SUM(CAST(word_count AS INTEGER)) AS total_words \
   FROM records GROUP BY category ORDER BY n DESC"

uv run folio serve examples/research-notes --port 3000 --actor agent:human
```

## Pattern this captures

A long-lived knowledge ledger that AI agents write into and humans
review. The cheap deterministic `word_count` derivation lets
dashboards and sorting work without invoking an LLM, and is a
template for richer derivations (`category`, `tags`, `summary`)
that you would add as `ai` derivations once an `ANTHROPIC_API_KEY`
is configured.
