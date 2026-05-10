# research-memory — Use Case 2.2: Structured Working Memory for Agents

A long-running research agent's intermediate findings. Each row is
a candidate that an agent surfaced; humans graduate it to
`verified` or `rejected`.

| Field | Owner | Notes |
|---|---|---|
| `query` | `agent:research`, `agent:human` | The question that surfaced this candidate. |
| `url`, `title`, `snippet` | `agent:research`, `agent:human` | What the agent extracted. |
| `status` | `agent:human` | `candidate` / `verified` / `rejected`. |
| `notes` | `agent:human` | Reviewer notes. |
| `domain` | derived (`python`) | Hostname extracted from `url` (no LLM call). |

## Try it

```bash
uv run folio validate examples/research-memory
uv run folio materialize examples/research-memory --actor agent:demo
uv run folio query examples/research-memory \
  "SELECT domain, COUNT(*) AS n FROM records GROUP BY domain ORDER BY n DESC"

uv run folio serve examples/research-memory --port 3000 --actor agent:human
```

## Pattern this captures

Tens to hundreds of intermediate findings, mostly written by the
agent, reviewed in batches by humans. The `domain` derivation is a
deliberately tiny, **deterministic** enrichment — no AI, no
network — so the cache lives forever and reviews focus on the
status / notes columns.
