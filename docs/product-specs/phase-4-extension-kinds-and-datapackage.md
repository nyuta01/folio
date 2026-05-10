# Phase 4 — Extension Kinds and Frictionless datapackage.json

The fifth executable slice of Folio. Phase 4 turns `kind` into a real
extension point by shipping the four representative extension kinds
named in §8.5 of the design overview and by emitting a Frictionless
Data Package descriptor for external tool interop.

```
my-sheet/
  derivations/
    legacy_id.yaml      # kind: import (Phase 1)
    industry_tag.yaml   # kind: ai     (Phase 1)
    revenue_q.yaml      # kind: sql    (Phase 4)
    weather.yaml        # kind: http   (Phase 4)
    enriched.yaml       # kind: python (Phase 4, depends on Phase 2 scripts/)
    parent_industry.yaml# kind: cross_sheet (Phase 4)
  datapackage.json      # NEW: emitted by `folio export datapackage`
```

## In scope

### Extension-kind plug point

- `src/folio/kinds/__init__.py` introduces a tiny registry:
  `register_kind(name, model_cls, executor)` so each kind ships as a
  cohesive triple of (Pydantic model, executor function, validation
  rules).
- `derivation.py` consults the registry to validate `kind: <name>`
  beyond the Phase 1 discriminated union. Unknown kinds remain
  rejected at parse time.

### sql kind

- `src/folio/kinds/_sql.py`: DuckDB SQL expression evaluated against
  the same in-memory `records` view used by `Sheet.query`. The kind
  body is `expression: <sql_fragment>` plus the standard
  `targets / inputs`. Single-target expression returns one column;
  multi-target requires `output_schema`-style mapping that names
  output columns.
- Read-only by construction (reuses `_query.ensure_select_only`).

### http kind

- `src/folio/kinds/_http.py`: HTTP API call via `httpx` (named in
  §20). Body keys: `url`, `method` (`GET` default), `headers`,
  `body_template` ({{ field }} expansion like the ai kind), and
  `response_path` (a JSONPath-style accessor) or
  `response_schema` for multi-target.
- Failures land as `failures` entries, never raised, mirroring the
  ai kind.

### python kind

- `src/folio/kinds/_python.py`: Calls a function in `scripts/`
  (Phase 2 script discovery + execution). Body keys: `script: <name>`,
  `function: <python_callable>`, `inputs` are passed as a single
  JSON-encoded argument. Output parsing follows the ai kind's
  text/json correspondence.

### cross_sheet kind

- `src/folio/kinds/_cross_sheet.py`: Read values from another sheet
  (`source_sheet: <relative-path>`) by `key_field` (matching the
  current record's primary key). Multi-target via `value_fields`.
  Cross-sheet stale detection includes the foreign sheet's
  `records.jsonl` content hash in the cache key.

### datapackage.json generation

- `src/folio/datapackage.py` maps the contract + records into a
  Frictionless Data Package descriptor per §14.2. The mapping
  table is finalized here.
- CLI: `folio export datapackage <sheet> --out datapackage.json`.
- Optional `--validate` runs the `frictionless` library against the
  generated descriptor.

## Out of scope (deferred to later phases)

- A general "third-party kind" plug-in entry-point. The registry is
  in-process only for Phase 4. External plug-ins are a future
  consideration.
- TOON output for the new kinds (already covered in Phase 3 at the
  `list_records` boundary; the kind drivers themselves return
  Python values).
- Multi-sheet workspaces. `cross_sheet` reads a sibling sheet by
  relative path; full workspace semantics land with Phase 6.

## Verification expectations

- Per-kind Pydantic v2 model rejection cases mirroring the Phase 1
  pattern (prompt vs prompt_ref, value_field vs value_fields).
- `sql` kind tests: SELECT-only enforcement, single + multi target,
  parameter passthrough.
- `http` kind tests: deterministic stub HTTPX transport + canned
  responses (similar to `StubAIClient`), template expansion in
  `body_template`, failure path captured as a failure entry.
- `python` kind tests: a fixture script that returns JSON, a script
  that raises, and a path-traversal rejection test.
- `cross_sheet` kind tests: matching primary key, missing foreign
  sheet, cycle detection across two sheets.
- datapackage.json: round-trip with `frictionless` against a Phase 0
  minimal sheet, mapping check for each `logicalType`.
- New CLI smoke `scripts/smoke-extension-kinds.sh` materializes one
  derivation per new kind with deterministic stubs.

## Reference scenario (target behavior)

```bash
$ folio materialize ./customers revenue_q --actor "agent:bot"
{"materialized": 100, "skipped": 0, "failures": [], "total_cost": 0.0}

$ folio export datapackage ./customers --out datapackage.json --validate
datapackage.json is valid (Frictionless Data Package v1)
```

## Suggested implementation breakdown

- **`FOLIO-H-020`**: kind registry, `sql` kind, `http` kind,
  matching tests, and the new smoke.
- **`FOLIO-H-021`**: `python` kind (depends on Phase 2 `FOLIO-H-014`)
  and `cross_sheet` kind, with cross-sheet stale-detection tests.
- **`FOLIO-H-022`**: `datapackage.json` generator, the
  `folio export datapackage` CLI verb, and round-trip validation
  against `frictionless`.

## Related

- Canonical specification: [`../design-docs/overview.md`](../design-docs/overview.md) §8.5, §14.2
- Frictionless Data Package: <https://specs.frictionlessdata.io/>
