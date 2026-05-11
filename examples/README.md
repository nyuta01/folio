# Folio examples

One sheet per use case from
[`docs/design-docs/overview.md` §2](../docs/design-docs/overview.md#2-use-cases).
Every example runs **fully offline** — no `ANTHROPIC_API_KEY`
required — by relying on the `python` and `cross_sheet`
derivation kinds.

| Sheet | Use Case | Derivation kinds | Skills |
|---|---|---|---|
| [`customers/`](customers) | 2.1 Customer Master Enrichment | `python` (country_code) + `cross_sheet` (current_revenue_usd) | `refresh-country-codes` |
| [`customer-revenue/`](customer-revenue) | (sidecar of customers) | — | `refresh-revenue` |
| [`research-memory/`](research-memory) | 2.2 Structured Working Memory for Agents | `python` (domain) | `triage-candidates` |
| [`research-notes/`](research-notes) | 2.3 Semi-structured Research Data Accumulation | `python` (word_count) | `weekly-digest` |
| [`onboarding/`](onboarding) | 2.4 Operational Worklist for Business Processes | `python` (progress) | `advance-onboarding` |

Every sheet ships at least one packaged operating procedure under
`skills/*.md`. Run `folio skill list <sheet>` to discover them, or
let an MCP client surface them as prompts.

## Quickstart

```bash
# Validate every example
for sheet in customers customer-revenue research-memory research-notes onboarding; do
  uv run folio validate "examples/$sheet"
done

# Materialize the four with derivations
for sheet in customers research-memory research-notes onboarding; do
  uv run folio materialize "examples/$sheet" --actor agent:demo
done

# Open one in the Viewer
uv run folio serve examples/customers --port 3000 --actor agent:human
# → http://127.0.0.1:3000/
```

## Why offline by default

Folio supports the `ai` derivation kind, but examples need to run
on a fresh clone with no secrets. Each `python` script is small,
deterministic, and a clear template for the AI version: replace
the script with an `ai` derivation against `claude-sonnet-4-6`
when an `ANTHROPIC_API_KEY` is configured.

## Editing in the Viewer

The default actor for `folio serve` is `agent:human`. Every
example marks the human-owned fields with
`x-editable-by: ["agent:human"]`, so:

- `company_name`, `country`, `industry_name` are inline-editable
  in `customers/`.
- `status` and `notes` are editable in `research-memory/`.
- `title`, `body`, `category`, `tags` are editable in
  `research-notes/`.
- `hire_name`, `role`, `owner`, `status`, and `checklist` are
  editable in `onboarding/`.

Editing a field writes a `human` provenance entry. Click any
non-editable cell to inspect its append-only history.
