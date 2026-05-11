<p align="center">
  <img src="https://raw.githubusercontent.com/nyuta01/folio/main/apps/desktop/build/icon-128.png" alt="Folio" width="96" height="96" />
</p>

<h1 align="center">folio-kit</h1>

Portable, AI-native data sheets. The Python distribution ships three
console scripts and a Python SDK for reading and writing typed data
sheets that humans and AI agents can both edit.

```
my-sheet/
├── contract.yaml         # required — ODCS subset
├── records.jsonl         # required — one JSON object per line
├── derivations/          # optional — derivation files (ai / python / sql / cross_sheet / import / http)
├── scripts/              # optional — reusable Python scripts
├── skills/               # optional — packaged operating procedures (markdown + YAML frontmatter)
├── provenance.jsonl      # append-only audit log
└── README.md             # optional, with typed frontmatter
```

## What you get

| Surface | Command | Purpose |
|---|---|---|
| CLI | `folio` | init, validate, query, list, count, upsert, delete, materialize, status, provenance, serve, script, skill, export |
| MCP server | `folio-mcp` | FastMCP server exposing the SDK over stdio or HTTP — plus one MCP prompt per skill — drop into Claude Desktop / Cursor / any MCP client |
| Viewer backend | `folio-viewer` | Local-only FastAPI server that powers the Folio Viewer desktop app and web UI |
| Python SDK | `from folio import open_sheet` | Programmatic access to the same operations as the CLI |

## Install

```bash
pipx install folio-kit
# or
uv tool install folio-kit
```

The distribution name is `folio-kit`; the on-disk command is `folio`.

## Quickstart

```bash
folio validate ./my-sheet
folio materialize ./my-sheet --actor agent:demo
folio query ./my-sheet "SELECT id, status FROM records LIMIT 5"
```

Programmatic:

```python
from folio import open_sheet

sheet = open_sheet("./my-sheet", actor="agent:demo")
sheet.upsert({"id": "cust_001", "company_name": "Acme", "country": "Japan"})
result = sheet.materialize()
print(result)   # {"materialized": 1, "skipped": 0, "failures": [], "total_cost": 0.0}
```

## Derivations

A `derivations/<field>.yaml` declares how a derived column is filled.
Folio ships six kinds:

- `ai` — call an LLM (Anthropic by default; injectable AIClient)
- `python` — run a reusable script from `scripts/`
- `sql` — DuckDB query against the sheet's records view
- `cross_sheet` — pull a value from a sibling Folio sheet (1:1 by PK)
- `import` — copy from a CSV / JSON file
- `http` — fetch from a URL

Every value comes with a provenance entry (actor, timestamp, input
hash, model + cost for `ai`). Re-runs are content-hashed and cached.

## Requirements

- Python 3.13+
- Optional: `ANTHROPIC_API_KEY` in the environment if you use `kind: ai`
  derivations against the default adapter. Bring-your-own `AIClient`
  for any other provider.

## Links

- **Source & full documentation:** https://github.com/nyuta01/folio
- **Specification:** [SPECIFICATION.md](https://github.com/nyuta01/folio/blob/main/SPECIFICATION.md) — the complete contract, formats, and semantics
- **Examples:** five working sheets under
  [`examples/`](https://github.com/nyuta01/folio/tree/main/examples/)
  (customers + its customer-revenue sidecar, research-notes,
  research-memory, onboarding) — each ships at least one
  `skills/*.md` operating procedure
- **Agent skills:** the
  [`folio-agent-skills`](https://www.npmjs.com/package/folio-agent-skills)
  npm package ships ready-to-install SKILL.md files for Claude / Cursor /
  any skills.sh-compatible agent runtime.
- **Issues & roadmap:** https://github.com/nyuta01/folio/issues

## License

MIT.
