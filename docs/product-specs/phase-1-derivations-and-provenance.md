# Phase 1 — Derivations, Materialization, Provenance, and Cache

The second executable slice of Folio. Phase 1 turns a Phase 0 sheet into
an AI-native one by adding derived fields and the audit log of how each
value was filled.

```
my-sheet/
  contract.yaml
  records.jsonl
  derivations/
    industry_tag.yaml          # one file per derived field
    summary.yaml
  provenance.jsonl              # auto-generated, append-only
```

`<user-cache>/folio/<sheet-id>/cache/` (per ADR-0008) stores cached
materialization results keyed by `input_hash` (§11).

## In scope

### Derivation parsing

- `src/folio/derivation.py`: Pydantic v2 models for
  `derivations/<field>.yaml`.
- Required keys: `targets` (always a list), `inputs` (list, may be
  empty), `kind` (Phase 1 supports `ai` and `import`), and the
  kind-specific body.
- Standard `materialization` block: `trigger: on_demand`,
  `respect_human_override: true`. Future triggers
  (`on_upstream_change`) are out of scope.
- The `output / targets / output_schema` correspondence table in §8.2
  of the design overview is enforced:
  - 1 target + `output: text` (string-typed field) ⇒ no `output_schema`.
  - 1 target + `output: json` (object/array-typed field) ⇒ no
    `output_schema` (driven by the field's `logicalType`).
  - 2+ targets ⇒ `output: json` and `output_schema` declaring each
    target's type.
- Prompt source: inline `prompt:` string (preferred) **or**
  `prompt_ref: prompts/<name>.md` (relative to the sheet directory).
  Only one of the two is permitted per derivation.
- Template expansion supports `{{ field_name }}` only (subset of
  Mustache / Jinja2).

### ai kind

- Driver: the `anthropic` Python SDK.
- Required keys: `model: <model_id>` (e.g., `claude-sonnet-4-6`),
  `prompt:` or `prompt_ref:`, `output: text | json`.
- Multi-target output_schema must match the contract `logicalType` of
  each target (string ↔ `string`, integer ↔ `integer`, etc.).
- Failures (rate limits, JSON parse errors, schema mismatch) become
  entries in the `failures` list of the `materialize` return value;
  they do **not** raise.
- `cost_usd` from the API response is recorded in
  `provenance.jsonl`.

### import kind

- Required keys: `source: <relative-path-or-command>`,
  `key_field`, `value_field`. Multi-value imports declare additional
  `value_fields:` mappings.
- Sources: CSV (`*.csv`), JSONL (`*.jsonl`), and JSON (`*.json`)
  files relative to the sheet directory. Out of process commands are
  out of scope for Phase 1.
- A row in the source whose `key_field` matches a record's primary
  key is matched; missing rows leave the target field unchanged.

### materialize operation

`materialize(targets=None, record_ids=None, force=False, actor)`:

- Default `targets=None` materializes every derived field in
  dependency order.
- Default `record_ids=None` materializes every stale record for the
  selected targets.
- `force=True` ignores `respect_human_override` and recomputes every
  selected record × field.
- Returns the §10.6 envelope `{materialized, skipped, failures, total_cost}`.
- Honors the cache: if `input_hash` is unchanged and the cached output
  exists, reuse it without invoking the kind.
- Honors `respect_human_override`: a `provenance` row whose `source`
  is `human_override` blocks recomputation unless `force=True`.

### materialization_status operation

`materialization_status(targets=None)` returns per-target
`{stale_count, total_count, last_run_at, last_actor}`.

### provenance.jsonl

- Append-only. Each materialization, import row match, and
  `human_override` (i.e., a manual `upsert_records` call that touches
  a derived field) writes a single line.
- The schema follows §9.1 exactly.
- The latest entry per `(record_id, field)` resolves the current
  source; `provenance(record_id, field, history=False)` returns it,
  and `history=True` returns the full append-only history.

### input_hash and cache

- `input_hash` is computed per §11 using **RFC 8785 (JCS, JSON
  Canonicalization Scheme)** over the derivation file hash, the
  prompt file hash (or inline prompt SHA-256), the model id (for
  `ai`), and the input field values.
- Cache root: `<user-cache>/folio/<sheet-id>/cache/<input_hash>`.
  `<sheet-id>` is `contract.id` (collision avoidance for sheets that
  share an id is tracked under design overview Appendix B).
- Cache values are JSON files containing the computed output and the
  metadata needed to reconstruct the provenance entry without a
  round-trip.

### Dependency resolution

- Build a DAG from `derivations/` mapping `target → inputs`.
- Materialize execution walks the topological sort.
- Cycles are an error at validate time and at materialize time.

### Stale detection

A derived field for a record is stale when the latest
`provenance.input_hash` for `(record_id, field)` differs from the
freshly computed `input_hash` (§8.3).

### CLI verbs

- `folio materialize <sheet> [<field>] [--force] [--ids <list>]
  --actor <a>`
- `folio status <sheet> [<field>]`
- `folio provenance <sheet> <record_id> <field> [--history]`

## Out of scope (deferred to later phases)

- Extension derivation kinds (`sql`, `http`, `python`,
  `cross_sheet`). Phase 4.
- TOON output formatting. Phase 3.
- MCP server. Phase 3.
- Viewer (FastAPI + React). Phase 5.
- README.md frontmatter convention for AI metadata. Phase 2.
- Reusable scripts under `scripts/` and language detection. Phase 2.
- Auto-trigger materialization (`on_upstream_change`). Future.
- Long-prompt versioning (`prompts/` versioning policy beyond file
  hash). Future.

## Verification expectations

When Phase 1 lands, `make verify` must include at least:

- Pydantic v2 models for `derivations/<field>.yaml` with parametrized
  rejection cases for malformed kind bodies, prompt + prompt_ref
  collision, target/output mismatch, and missing `output_schema` for
  multi-target derivations.
- Deterministic unit tests for:
  - `input_hash` calculation (RFC 8785 stability across key order
    and float representation).
  - Stale detection across edits to the prompt body, the derivation
    file, the input value, and the model id.
  - Dependency resolution (topological order, cycle detection).
  - `provenance.jsonl` append + latest-resolution + history.
  - Cache hit / miss / invalidation.
- A mocked-Anthropic-SDK integration test that walks the §23.3
  scenario from the design overview without making real network
  calls.
- An import-kind integration test against a CSV fixture.
- CLI smoke (`scripts/smoke-materialize.sh`) using a stubbed `ai`
  kind so the gate stays deterministic offline.

The repository virtual environment, the user cache, and the
materialize stub binary all live **outside** sample sheets per
ADR-0008. Smoke fixtures must not write inside `<sheet>/.cache/`.

## Reference scenario (target behavior)

Replays §23.3 of the design overview. Mocked `ai` calls return a
fixed industry tag per company name.

```bash
$ folio validate ./customers
✓ contract.yaml is valid
✓ derivations/industry_tag.yaml is valid
✓ All records conform to schema

$ folio query ./customers \
    "SELECT COUNT(*) AS n FROM records WHERE industry_tag IS NULL"
[{"n": 2}]

$ folio materialize ./customers industry_tag \
    --actor "agent:enrichment-bot"
{"materialized": 2, "skipped": 0, "failures": [], "total_cost": 0.0017}

$ folio query ./customers \
    "SELECT industry_tag, COUNT(*) AS n FROM records GROUP BY 1"
[{"industry_tag": "Manufacturing", "n": 1},
 {"industry_tag": "Software", "n": 1},
 {"industry_tag": "Agriculture", "n": 1}]

$ echo '{"id": "cust_003", "industry_tag": "AgTech"}' \
    | folio upsert ./customers --file - --actor "human:yuta"
{"inserted": 0, "updated": 1, "total": 3}

$ folio provenance ./customers cust_003 industry_tag --history
[
  {"source": "ai", "actor": "agent:enrichment-bot",
   "at": "2026-05-09T10:05:00Z", "input_hash": "sha256:...", ...},
  {"source": "human_override", "actor": "human:yuta",
   "at": "2026-05-09T11:00:00Z", ...}
]
```

## Suggested implementation breakdown

To keep loops bounded, Phase 1 ships as four backlog tasks:

- **`FOLIO-H-009`**: derivation.yaml parsing (Pydantic), validate-time
  cycle detection, and `import` kind execution.
- **`FOLIO-H-010`**: `input_hash` (RFC 8785), cache layer at
  `<user-cache>/folio/<sheet-id>/cache/`, and `provenance.jsonl` read/
  append helpers.
- **`FOLIO-H-011`**: `ai` kind via the `anthropic` SDK with prompt
  template expansion, multi-target `output_schema`, retry policy, and
  recorded `cost_usd`.
- **`FOLIO-H-012`**: CLI verbs (`materialize`, `status`, `provenance`)
  and `scripts/smoke-materialize.sh` (deterministic, mocked AI).

Each task gets its own active plan and ADR additions when its
implementation reveals a binding choice (e.g., a deterministic stub
mode for `ai`).

## Related

- Canonical specification: [`../design-docs/overview.md`](../design-docs/overview.md)
- Decision log: [`../design-docs/adrs/`](../design-docs/adrs/)
- Phase 0 spec: [`phase-0-minimum-sheet.md`](phase-0-minimum-sheet.md)
- Active plans: [`../exec-plans/active/`](../exec-plans/active/)
