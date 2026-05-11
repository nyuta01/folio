# Phase 0 — Minimum Sheet

The first executable slice of Folio. A Phase 0 sheet has only the two
required files defined by the specification:

```
my-sheet/
  contract.yaml      # required, ODCS-subset structure declaration
  records.jsonl      # required, may be empty
```

Phase 0 does not introduce derivations, provenance, scripts, attachments,
caching, MCP, or the Viewer.

## In scope

- `contract.yaml` validation via Pydantic v2:
  - `apiVersion`, `kind`, `id`, `name`, `version`, optional `description`.
  - `schema` is a single-element list (1 sheet = 1 model).
  - Each property has a `name`, `logicalType` from
    `string | integer | number | boolean | date | timestamp | array | object`,
    optional `primaryKey`, `required`, `description`,
    `x-derived`, `x-inputs`, `x-editable-by`.
  - Exactly one `primaryKey` field across all properties.
- `records.jsonl` reading via DuckDB:
  - Empty file is valid.
  - Each line is a JSON object whose keys match property names.
- Core operations on the SDK surface:
  - `get_contract()`
  - `query(sql, params=None)` — SELECT-only enforcement.
  - `list_records(filter=None, fields=None, limit=50, cursor=None)`
    returning `format=json`.
  - `get_record(id, fields=None)`.
  - `upsert_records(records, actor)`.
  - `delete_records(ids, actor)`.
- Single-writer concurrency: acquire `.lock` directly under the sheet before
  writes, default 30 second timeout.
- Atomic writes: `records.jsonl` updates use temp file + rename.
- `editable_by` validation: only enforced when present, pattern-match against
  the supplied `actor` string.
- `folio` CLI verbs:
  `validate`, `query`, `list`, `count`, `upsert`, `delete`.

## Out of scope (deferred to later phases)

- Derivation execution (`materialize`, `derivations/`, `provenance.jsonl`,
  cache, AI calls). See Phase 1.
- Reusable scripts under `scripts/` and README frontmatter conventions. See
  Phase 2.
- TOON output and the MCP server. See Phase 3.
- Extension derivation kinds (`sql`, `http`, `python`, `cross_sheet`) and
  `datapackage.json` generation. See Phase 4.
- Viewer (FastAPI + React). See Phase 5.

## Verification expectations

When Phase 0 lands, `make verify` must include at least:

- `python_test`: `pytest` over the contract validation, JSONL reading, lock
  semantics, and editable_by enforcement.
- `cli_smoke`: a deterministic shell script that builds a temporary sheet,
  runs each CLI verb, and asserts the expected output and exit codes.

The sample sheet used by smoke tests must remain `tar`-portable: it must not
write caches, virtual environments, or audit logs into its own directory.
Implementation-specific artifacts go under `.folio-cache/` or
`.folio-runtime/` outside the sheet.

## Reference scenario (target behavior)

```bash
$ folio validate ./minimal-sheet
✓ contract.yaml is valid
✓ All records conform to schema

$ folio count ./minimal-sheet
1

$ folio query ./minimal-sheet "SELECT id, name FROM records"
[{"id":"item_001","name":"first"}]

$ folio upsert ./minimal-sheet --file - --actor "human:alice" <<EOF
{"id":"item_002","name":"second"}
EOF
1 upserted
```

## Related

- Canonical specification: [`docs/design-docs/overview.md`](../design-docs/overview.md)
- Decision log: [`docs/design-docs/adrs/`](../design-docs/adrs/)
- Active plans:
  [`docs/exec-plans/active/`](../exec-plans/active/)
