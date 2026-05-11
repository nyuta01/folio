# Folio — Specification

**Status:** v3.0.0, tracks
[Open Data Contract Standard (ODCS) v3.0.0](https://github.com/bitol-io/open-data-contract-standard).
Single, comprehensive normative summary of the Folio specification.
Intended to be loaded as the canonical reference by both humans and AI
agents.

> **Living document.** The machine-parseable tables in this file are
> verified against the reference implementation by the project's
> verifier. See §13 for the verifier contract and what is guaranteed
> to be in sync. If the verifier fails, the document — not the code —
> is wrong, and the document must be updated before the next release.

---

## Contents

1. [What Folio is](#1-what-folio-is)
2. [Sheet anatomy](#2-sheet-anatomy)
3. [Data format](#3-data-format)
4. [Validation summary](#4-validation-summary)
5. [Materialize lifecycle](#5-materialize-lifecycle)
6. [Cache & runtime layout](#6-cache--runtime-layout)
7. [Surfaces](#7-surfaces)
8. [Exceptions](#8-exceptions)
9. [Configuration](#9-configuration)
10. [Concept glossary](#10-concept-glossary)
11. [External references](#11-external-references)
12. [Decision principles](#12-decision-principles)
13. [Verification](#13-verification)

---

## 1. What Folio is

A **Folio sheet** is a directory holding a typed contract, JSONL records,
optional derivations, and an append-only audit log. Folio is

- a small **specification** (this file plus the ODCS-aligned contract
  schema),
- a **Python reference implementation**,
- and four read/write **surfaces** that all touch the same directory: the
  CLI (`folio`), the SDK (`folio` Python package), the MCP server
  (`folio-mcp`), and the local Viewer (`folio-viewer`, FastAPI + React).

The sheet is the **system of record.** Caches, virtualenvs, and runtime
state live outside the sheet (see §6). Anything inside the sheet
directory is part of the contract and travels with the data when you
`tar` it.

### 1.1 Priorities (resolved in this order)

1. **Simplicity.** The minimum sheet is two files. Few rules to remember.
2. **Portability.** A sheet is fully transportable as a tarball; nothing
   environment-dependent lives inside.
3. **Generality.** Extension points are explicit; the spec is not tied
   to a language or use case.

When two priorities conflict, simplicity wins.

### 1.2 Non-goals

- Not a 100M-row analytics warehouse — designed for **tens to hundreds
  of thousands of records per sheet**.
- Not a real-time collaborative editor — a single-writer `.lock` keeps
  semantics simple.
- Not a hosted service — the local Viewer binds to `127.0.0.1` only.

---

## 2. Sheet anatomy

A sheet is a directory laid out as follows. Required files are marked.
Folio never writes anything outside this layout into the sheet
directory.

```
my-sheet/
├── contract.yaml         # REQUIRED — schema + identity (§3.1)
├── records.jsonl         # REQUIRED — JSON Lines data (§3.2)
├── provenance.jsonl      # written by Folio on materialize; safe to
│                         # commit (§3.3); created on first append
├── derivations/          # optional — *.yaml rules that fill x-derived
│   └── *.yaml            # fields (§3.4)
├── scripts/              # optional — Python referenced by python
│   ├── *.py              # derivations and `folio script run`
│   └── requirements.txt  # optional — if present, Folio creates a
│                         # per-sheet venv outside the sheet
├── prompts/              # optional — markdown referenced by ai
│   └── *.md              # derivations
├── README.md             # optional — typed YAML frontmatter (§3.6)
└── .lock                 # filelock (30s timeout); Folio manages it
```

Two specific things are deliberately **not** in the sheet:

- **No cache files.** The cache lives at
  `<user-cache>/folio/<sheet-id>/cache/`.
- **No virtualenv.** When `scripts/requirements.txt` exists, Folio
  creates a venv at `<user-cache>/folio/<sheet-id>/runtime/venv/`.

If you cannot redo it, it is in the sheet. If you can recompute it, it
is not.

---

## 3. Data format

### 3.1 `contract.yaml`

YAML, UTF-8, ODCS v3.0.0 subset. Read once when a `Sheet` is opened.

#### 3.1.1 Top-level fields

<!-- spec-table: contract-fields -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `apiVersion` | string | yes | Must be `v3.0.0`. |
| `kind` | string | yes | Must be `DataContract`. |
| `id` | string | yes | Stable slug; scopes the cache and runtime directories at `<user-cache>/folio/<id>/...`. |
| `name` | string | yes | Human-readable display name. |
| `version` | string | yes | Semver `MAJOR.MINOR.PATCH`. Bump major on breaking record changes. |
| `description` | string \| null | no | Free-form. Multi-line YAML strings are accepted. |
| `schema` | array | yes | **Exactly one** entry. (1 sheet = 1 model.) |

Unknown top-level fields are tolerated (preserved by the loader so that
forward-compatible additions do not error). `Sheet(...)` rejects only
those listed under §4.

#### 3.1.2 `schema[]`

<!-- spec-table: schema-fields -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `name` | string | yes | Logical table name. Convention: `items`. |
| `physicalType` | string | no | Defaults to `jsonl`. The reference implementation only exercises `jsonl`; the field is reserved for future formats. |
| `properties` | array | yes | One entry per column. Order is preserved. Must contain at least one. |

Unknown attributes inside a schema entry are **rejected** (`extra="forbid"`).

#### 3.1.3 `properties[]`

```yaml
- name: country_code
  logicalType: string
  description: ISO 3166-1 alpha-2.
  required: false
  primaryKey: false
  x-derived: true
  x-inputs: [country]
  x-editable-by: ["agent:human"]
```

<!-- spec-table: property-fields -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `name` | string | yes | ASCII letters, digits, `_`, `-`. |
| `logicalType` | enum | yes | See §3.1.4. |
| `description` | string \| null | no | Free-form. |
| `required` | boolean | no | Default `false`. Enforced on `upsert_records`. |
| `primaryKey` | boolean | no | Default `false`. **Exactly one** property must be `true`. Composite keys not supported. |
| `x-derived` | boolean | no | Default `false`. When `true`, requires `x-inputs` and a matching derivation. |
| `x-inputs` | array of strings | conditional | Required when `x-derived: true`. Must reference declared properties. |
| `x-editable-by` | array of strings \| null | no | Default `null` ⇒ field is not human-editable. `fnmatch` patterns matched against the actor on every direct write. |

Unknown attributes on a property are **rejected** (`extra="forbid"`).
A typo such as `primaryKeys: true` fails at load time.

`x-editable-by` examples (case-sensitive, POSIX `fnmatch(3)`):

```yaml
x-editable-by: ["agent:human"]            # exactly that one actor
x-editable-by: ["agent:ops:*"]            # any actor under agent:ops:
x-editable-by: ["agent:human:*", "*"]     # second pattern matches anyone
```

`*` matches every actor — useful for development sheets, never for
production.

#### 3.1.4 `logicalType` enum

<!-- spec-table: logical-types -->

| Folio | JSON shape | Frictionless export |
|---|---|---|
| `string` | string | `string` |
| `integer` | integer | `integer` |
| `number` | number | `number` |
| `boolean` | boolean | `boolean` |
| `date` | string `YYYY-MM-DD` | `date` |
| `timestamp` | string ISO-8601 with offset | `datetime` |
| `array` | array | `array` |
| `object` | object | `object` |

Folio does not validate inner shape for `array` / `object` — that is
an application concern.

#### 3.1.5 Multilingual descriptions

The current reference implementation accepts only a plain `string` for
`description`. ODCS itself permits a locale mapping; future Folio
versions may extend the model. Use a separate property when you need
translations today.

---

### 3.2 `records.jsonl`

Line-delimited JSON ([JSON Lines](https://jsonlines.org/)), UTF-8, **one
JSON object per line**, no enclosing array.

```jsonl
{"id": "cust_001", "company_name": "Acme Manufacturing", "country": "Japan"}
{"id": "cust_002", "company_name": "DataFlow",          "country": "United States"}
```

#### 3.2.1 Encoding & line semantics

- **Encoding:** UTF-8. No BOM.
- **Line terminator:** `\n`. CRLF accepted on read; Folio rewrites to `\n`.
- **Empty lines:** ignored.
- **Trailing newline:** Folio always writes one. Files without one are
  accepted on read.

#### 3.2.2 Per-record invariants

For each non-empty line:

1. Must parse as a JSON **object** (not a string, not an array).
2. Must include the contract's primary key as a non-null value.
3. Required fields (per the contract) must be present and non-null on
   write (`upsert_records` enforces).
4. May include extra fields not declared in the contract — Folio
   preserves them verbatim across writes (no silent drop).

#### 3.2.3 Atomicity

`Sheet.upsert_records`, `Sheet.delete_records`, and `Sheet.materialize`
write `records.jsonl` through a **temp file + rename**:

```
records.jsonl.tmp.<pid>     ← write the new content
records.jsonl               ← atomic rename over the old file
```

A reader holding an open file descriptor on `records.jsonl` sees a
complete older snapshot. A new reader sees the new file. There is no
torn state.

A `.lock` file (filelock, 30s timeout) serializes writers
(single-writer). Reads do not take the lock.

#### 3.2.4 Order

Folio does **not** guarantee record order across writes.
`upsert_records` keeps the relative order of pre-existing rows but
appends new ones at the end. If you need a stable order, use an
`ORDER BY` in your query.

#### 3.2.5 DuckDB view

Folio exposes records to DuckDB as a view named `records`. **Only
`SELECT` is allowed**; INSERT / UPDATE / DELETE / DDL are rejected at
the Folio layer. Use `upsert_records` / `delete_records` to mutate.

```python
sheet.query("SELECT * FROM records WHERE country = ?", ["Japan"])
```

`Sheet.list_records` accepts `limit` (default `50`) and `cursor`. The
cursor is an opaque string Folio gives you back; pass it on the next
call to continue.

---

### 3.3 `provenance.jsonl`

JSON Lines, **append-only by convention.** One line per successful
materialized cell write. Folio never rewrites or compacts; the file
ships inside the sheet so the audit trail moves with the data.

```jsonl
{"record_id":"cust_001","field":"country_code","source":"python",
 "actor":"agent:demo","at":"2026-05-10T10:16:35Z",
 "input_hash":"sha256:ce82..."}
```

#### 3.3.1 Schema

<!-- spec-table: provenance-fields -->

| Field | Always present | Notes |
|---|:-:|---|
| `record_id` | yes | Primary-key value of the record. |
| `field` | yes | Field that was written. |
| `source` | yes | One of the values in §3.3.3. |
| `actor` | yes | Free-form string passed by the writer (Folio does not rewrite it). |
| `at` | yes | UTC ISO-8601, second precision. |
| `input_hash` | when derived | `sha256:…`; absent for `source: human_override`. |
| `model` | for `ai` | Model id (e.g. `claude-sonnet-4-6`). |
| `cost_usd` | for `ai` | Number, or `null` for unknown models. |

#### 3.3.2 What gets logged

- **`Sheet.materialize`** appends one entry per successful materialized
  cell. Cache hits do **not** append — the prior line is the canonical
  record. Failures do not log.
- **Direct writes** (`Sheet.upsert_records`, `Sheet.delete_records`)
  do **not** write provenance entries today. The writer (a human or an
  agent) is expected to append a `source: human_override` line through
  a separate workflow if it wants the override semantics described in
  §5.
- A no-op upsert (same value) writes nothing.

#### 3.3.3 `source` enum

<!-- spec-table: provenance-source -->

| Value | Written by | Notes |
|---|---|---|
| `ai` | `Sheet.materialize` (kind `ai`) | Adds `model` and optional `cost_usd`. |
| `import` | `Sheet.materialize` (kind `import`) | — |
| `python` | `Sheet.materialize` (kind `python`) | — |
| `sql` | `Sheet.materialize` (kind `sql`) | — |
| `http` | `Sheet.materialize` (kind `http`) | — |
| `cross_sheet` | `Sheet.materialize` (kind `cross_sheet`) | — |
| `human_override` | external (manual / future API) | Recognized on read; instructs `materialize` to skip the cell unless `force=True` or `respect_human_override=False`. |

#### 3.3.4 What Folio deliberately omits from a line

- Previous and new values (the previous line is the prior value; the
  new value is in `records.jsonl`).
- Free-form notes (use a dedicated `notes` column on the contract).

#### 3.3.5 Read-back semantics

`Sheet.materialize` reads only the **latest** entry per cell. If the
latest line says `source: human_override`, materialize skips. Folio
always appends in time order, so the last line is authoritative by
construction.

---

### 3.4 `derivations/*.yaml`

A **derivation** is a YAML file that fills one or more `x-derived`
fields. Folio walks `derivations/` alphabetically for stable execution
order; the file basename is free-form.

#### 3.4.1 Common shape

<!-- spec-table: derivation-base-fields -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `targets` | array of strings | yes | Field names this derivation writes. Each must be `x-derived: true` on the contract. |
| `inputs` | array of strings | no | Default `[]`. Field names whose changes invalidate the cache. Must exist on the contract. |
| `kind` | enum | yes | One of: `ai`, `import`, `python`, `sql`, `http`, `cross_sheet`. |
| `materialization` | object | no | `{ respect_human_override: bool }`. Default `respect_human_override: true`. |

For multi-target derivations (more than one entry in `targets`),
declare `output_schema` (a `{name: type}` mapping) so Folio knows
which output goes to which target. Single-target derivations can omit
it.

`output` is `text` (default; the kind returns one scalar) or `json`
(the kind returns a JSON object that maps `target → value`). Some
kinds make this implicit (see per-kind tables).

#### 3.4.2 `ai` kind

Calls an LLM via the `AIClient` Protocol (Anthropic SDK by default;
ships with `StubAIClient` for offline tests).

<!-- spec-table: derivation-ai-fields -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `kind` | `"ai"` | yes | Discriminator. |
| `model` | string | yes | Model id passed to the AI client. |
| `prompt` | string | no | Inline prompt body. Mutually exclusive with `prompt_ref`. |
| `prompt_ref` | string | no | Path to a markdown file under `prompts/`. Mutually exclusive with `prompt`. |
| `output` | enum | yes | `text` (one scalar) or `json` (object mapping targets to values). |
| `output_schema` | object | conditional | `{name: type}` — required when `output: json` and for multi-target derivations. |

#### 3.4.3 `import` kind

Reads from a local CSV / JSONL / JSON file in the sheet directory.

<!-- spec-table: derivation-import-fields -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `kind` | `"import"` | yes | Discriminator. |
| `source` | string | yes | Path relative to the sheet root. Extension `.csv` / `.jsonl` / `.json` selects the parser. |
| `key_field` | string | yes | Name of the column in `source` that joins to the input field. |
| `value_field` | string | conditional | Name of the column to copy. Required for single-target derivations. |
| `value_fields` | object | conditional | `{target_name: source_column}` mapping for multi-target derivations. |

#### 3.4.4 `python` kind

Runs `scripts/<name>.py` as a subprocess. If `scripts/requirements.txt`
exists, the subprocess runs inside a per-sheet virtualenv created on
first use under `<user-cache>/folio/<sheet-id>/runtime/venv/`.

<!-- spec-table: derivation-python-fields -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `kind` | `"python"` | yes | Discriminator. |
| `script` | string | yes | Basename (no extension) of a file under `scripts/`. The script reads a single JSON object from stdin (the inputs) and writes the result to stdout. |
| `output` | enum | no | `text` (default) or `json`. |
| `output_schema` | object | conditional | Required for multi-target derivations. |

#### 3.4.5 `sql` kind

Evaluates a DuckDB SELECT-only expression against the `records` view.

<!-- spec-table: derivation-sql-fields -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `kind` | `"sql"` | yes | Discriminator. |
| `expression` | string | yes | A DuckDB expression. Inputs are bound as `?` parameters in the order they appear in `inputs`. |
| `output_schema` | object | conditional | Required for multi-target derivations. |

#### 3.4.6 `http` kind

Calls a templated HTTP endpoint via the `HTTPTransport` Protocol
(stub-only by default).

<!-- spec-table: derivation-http-fields -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `kind` | `"http"` | yes | Discriminator. |
| `url` | string | yes | URL template; `{field}` placeholders are filled from the input record. |
| `method` | enum | no | `GET` (default) or `POST`. |
| `headers` | object | no | Header → value mapping; values may use `{field}` templates. |
| `body_template` | string | no | Body template string (POST only); JSON-encoded after substitution. |
| `response_path` | string | no | Dotted path into the JSON response to extract the result. |
| `response_schema` | object | conditional | Required for multi-target derivations. |

#### 3.4.7 `cross_sheet` kind

Joins to a sibling sheet 1:1 by primary key.

<!-- spec-table: derivation-cross-sheet-fields -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `kind` | `"cross_sheet"` | yes | Discriminator. |
| `source_sheet` | string | yes | Path to a sibling Folio sheet directory (relative to this sheet, or absolute). |
| `key_field` | string | yes | Field on the source sheet to match against the input. |
| `value_field` | string | conditional | Field to copy. Required for single-target derivations. |
| `value_fields` | object | conditional | `{target_name: source_field}` mapping for multi-target derivations. |

#### 3.4.8 Dependency resolution

Derivations may target fields that other derivations input. Folio
topologically sorts (Kahn's algorithm) at materialize time. A cycle
aborts the run with `DerivationError`.

#### 3.4.9 `input_hash` composition

The cache key for one (derivation × record) is `sha256` over the
concatenation of:

- The canonical JSON of every value listed in `inputs` (key-sorted).
- The SHA-256 of the derivation YAML file itself.
- Kind-specific extras:
  - `ai` — the resolved `prompt_body` (after `prompt_ref` is read).
  - `import` — the SHA-256 of `source`.
  - `python` — the SHA-256 of `scripts/<script>.py`.
  - `cross_sheet` — the SHA-256 of the foreign sheet's `records.jsonl`.

If any of those changes, the cache misses, the kind re-runs, and a
fresh provenance line is appended.

---

### 3.5 `scripts/`

Optional. Reusable Python referenced by `python` derivations and the
`folio script run` CLI verb.

```yaml
# derivations/area.yaml
targets: [area_sqkm]
inputs: [country]
kind: python
script: country_to_area     # ⇒ scripts/country_to_area.py
```

If `scripts/requirements.txt` exists, Folio creates a per-sheet venv
on first use and reuses it.

A script reads a single JSON object from stdin (inputs keyed by name)
and writes its result to stdout. For multi-target derivations, the
result is a JSON object keyed by target name.

### 3.6 `README.md`

Optional. When present and parseable, the YAML frontmatter is
read by Folio and surfaced in the Viewer.

<!-- spec-table: readme-frontmatter -->

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `purpose` | string | yes | One- or two-sentence summary of what the sheet is for. |
| `default_actor` | string | yes | Default actor string used by the Viewer when none is supplied. |
| `tags` | array of strings | no | Free-form labels. |
| `links` | object (string→string) | no | Useful URLs (issue tracker, runbook, etc.). |
| `agent_skills` | array of strings | no | Hint to agents about which skills are relevant. |

Unknown frontmatter keys raise a load error.

### 3.7 `prompts/`

Optional. Markdown files referenced by `ai` derivations via
`prompt_ref`. Folio reads the file's bytes verbatim into the
derivation's resolved `prompt_body`; the SHA-256 of that body
participates in `input_hash` (see §3.4.9).

### 3.8 `.lock`

Single-writer lock managed by Folio (filelock, 30s timeout). All write
operations acquire it; reads do not. Stale locks are reclaimed on the
next acquisition attempt — `filelock` itself recovers if the holder
process is gone.

---

## 4. Validation summary

`Sheet(...)` construction and `folio validate` reject:

- Contract violations:
  - Zero or more than one `primaryKey: true` properties.
  - A `logicalType` not in §3.1.4.
  - `x-derived: true` without `x-inputs`.
  - `x-inputs` referencing a non-existent property.
  - Property `name` containing characters outside `[A-Za-z0-9_-]`.
  - Missing any of `apiVersion`, `kind`, `id`, `name`, `version`.
  - Unknown attributes on a `properties[]` entry or a `schema[]` entry.
  - A second `schema[]` entry.
- Records that fail any invariant in §3.2.2.
- Derivation files whose:
  - `targets` reference a non-`x-derived` property.
  - `inputs` reference a missing property.
  - Multi-target form is missing `output_schema` (or
    `value_fields` / `response_schema` per kind).
- Cyclic derivation dependencies.

Failures during `materialize` are reported per-record-per-field on the
result envelope, not raised — a 5,000-row materialize does not abort
on one bad row.

---

## 5. Materialize lifecycle

```
                      ┌─────────────────────────────────────┐
                      │ derivations/* (topologically sorted) │
                      └─────────────────────────────────────┘
                                       │
                       for each derivation:
                                       │
                       for each target record:
                                       │
                  ┌────────────────────┼────────────────────┐
                  │                    │                    │
            input_hash =          cache hit?            execute kind
            sha256(canonical       (yes → skip)         (ai/import/...)
            JSON of inputs                  │                    │
            + derivation file +              ▼                    ▼
            kind-specific bytes)         skip               update record
                                                      append provenance line
                                                           cache result
```

Per-cell skip rules (defaults: `respect_human_override=true`,
`force=false`):

- Latest provenance entry says `source: human_override` → **skip**.
- `input_hash` matches the cache → **skip**.
- Otherwise → execute, write, append provenance, cache.

`force=True` ignores both the cache and `human_override` and
recomputes. `respect_human_override=false` ignores only the override
guard.

The materialize result envelope:

```json
{
  "materialized": <int>,
  "skipped": <int>,
  "failures": [{"record_id": "...", "field": "...", "error": "..."}]
}
```

`Sheet.materialization_status` returns counts per derived field
(`ai_count`, `import_count`, `python_count`, `sql_count`, `http_count`,
`cross_sheet_count`, `human_override_count`, plus a `derivation_kind`).

---

## 6. Cache & runtime layout

| Item | Location | Why |
|---|---|---|
| Records, contract, derivations, scripts, prompts | inside the sheet | system of record |
| Provenance | inside the sheet | tamper-evident; ships with the data |
| Cache (per `derivation × input_hash`) | `<user-cache>/folio/<sheet-id>/cache/` | recoverable; not deterministic |
| Per-sheet runtime venv | `<user-cache>/folio/<sheet-id>/runtime/venv/` | environment-dependent |
| `.lock` | inside the sheet | tied to the writer process |

`<user-cache>` follows the platform convention (`~/Library/Caches` on
macOS, `~/.cache` on Linux, `%LOCALAPPDATA%` on Windows). Removing
the cache is always safe — Folio rebuilds on the next materialize.

The cache file format is a JSON envelope per (derivation × record):

```json
{
  "input_hash": "sha256:...",
  "value": <kind-specific-payload>,
  "computed_at": "2026-05-10T10:16:35Z"
}
```

For multi-target derivations, `value` is a JSON object mapping target
name to value (the same structure that materialize unpacks into
records).

---

## 7. Surfaces

The Python SDK is the only place that touches files directly. The
other three surfaces import the SDK and project it onto their
transport.

### 7.1 CLI (`folio`)

Typer command tree, JSON to stdout. Verbs:

<!-- spec-table: cli-verbs -->

| Verb | One-liner |
|---|---|
| `validate` | Validate `contract.yaml`, `records.jsonl`, and README frontmatter. |
| `query` | Execute DuckDB SQL against the sheet's records view. |
| `list` | List records as a JSON envelope (records may be `json` or `toon`). |
| `count` | Count records, optionally with a WHERE-clause filter. |
| `upsert` | Insert or update records by `primaryKey`. |
| `delete` | Delete records by `primaryKey` id. |
| `materialize` | Materialize derived fields. Defaults to every derivation. |
| `status` | Print materialization counts per derived field. |
| `provenance` | Print provenance for a record × field. |
| `script` | Sub-app: `script list`, `script run <name>`. |
| `skill` | Sub-app: `skill list`, `skill show <name>`, `skill validate`. Packaged operating procedures under `<sheet>/skills/`. |
| `export` | Sub-app: `export datapackage` (Frictionless descriptor). |
| `serve` | Run the local Viewer (delegates to `folio-viewer`). |

All verbs accept `--actor <string>` where applicable; `--actor` is
required by every mutating verb.

### 7.2 SDK (`folio` Python package)

Entry point: `Sheet(path)`. Public methods:

<!-- spec-table: sdk-methods -->

| Method | Signature (abbreviated) |
|---|---|
| `get_contract` | `() -> Contract` |
| `list_records` | `(filter=None, fields=None, limit=50, cursor=None, params=None, format="json") -> dict` |
| `get_record` | `(id, fields=None) -> dict \| None` |
| `upsert_records` | `(records, actor) -> {"inserted": int, "updated": int, "total": int}` |
| `delete_records` | `(ids, actor) -> {"deleted": int, "remaining": int}` |
| `query` | `(sql, params=None) -> list[dict]` |
| `materialize` | `(targets=None, record_ids=None, force=False, actor, ai_client=None, http_transport=None) -> dict` |
| `materialization_status` | `(targets=None) -> dict[str, dict]` |
| `provenance` | `(record_id, field, history=False) -> dict \| list` |
| `add_property` | `(prop, *, actor) -> Contract` |
| `update_property` | `(name, *, actor, new_name=None, logical_type=None, description=None, required=None, editable_by=None) -> Contract` |
| `delete_property` | `(name, *, actor) -> Contract` |
| `run_script` | `(name, args=None, timeout_seconds=60.0) -> ScriptResult` |
| `list_skills` | `() -> list[Skill]` |
| `get_skill` | `(name) -> Skill \| None` |
| `render_skill` | `(name, args=None) -> str` |

All writes acquire the sheet `.lock` and use the temp-file-rename
path; reads do not take the lock.

`list_skills` / `get_skill` / `render_skill` operate on packaged
markdown files under `<sheet>/skills/` — short, named operating
procedures the sheet carries for its agent / human users. See §11.

### 7.3 MCP (`folio-mcp`)

FastMCP server exposing the SDK as tools so MCP-compatible runtimes
(Claude Desktop, etc.) can read and write sheets without bespoke glue.

<!-- spec-table: mcp-tools -->

| Tool | Mirrors SDK method |
|---|---|
| `get_contract` | `Sheet.get_contract` |
| `query` | `Sheet.query` |
| `list_records` | `Sheet.list_records` |
| `get_record` | `Sheet.get_record` |
| `upsert_records` | `Sheet.upsert_records` |
| `delete_records` | `Sheet.delete_records` |
| `materialize` | `Sheet.materialize` |
| `materialization_status` | `Sheet.materialization_status` |
| `provenance` | `Sheet.provenance` |

In addition to tools, the MCP server publishes one **prompt** per
skill discovered under each sheet's `skills/` directory. Prompt
names use the form `<sheet-id>:<skill-name>` to avoid collisions
when one server hosts multiple sheets. Arguments declared on a skill
are surfaced as the prompt's argument schema; `prompts/get` returns
the rendered markdown body with substitutions filled in.

### 7.4 Viewer (`folio-viewer`)

FastAPI + React, **`127.0.0.1` only** by default. REST routes mirror
SDK methods. All mutating verbs require a CSRF cookie + `X-CSRF-Token`
header. The server emits materialize lifecycle frames on
Server-Sent Events (`text/event-stream`).

<!-- spec-table: viewer-routes -->

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/csrf` | Issue a CSRF cookie + token (call before any mutating verb). |
| GET | `/api/contract` | Return the contract document. |
| POST | `/api/contract/properties` | Append a new property. |
| PATCH | `/api/contract/properties/{name}` | Update a property (rename / type / description / required / editable-by). |
| DELETE | `/api/contract/properties/{name}` | Delete a property (refuses PK / x-derived / x-inputs-referenced). |
| GET | `/api/records` | Paginated list. |
| GET | `/api/records/{record_id}` | Single record. |
| POST | `/api/records` | Upsert one record. |
| DELETE | `/api/records` | Bulk delete by ids. |
| POST | `/api/query` | Execute a DuckDB SELECT. |
| GET | `/api/status` | Materialization counts per derived field. |
| POST | `/api/materialize` | Materialize derived fields (full or targeted). |
| GET | `/api/provenance` | Provenance for a record × field (`?record_id=...&field=...&history=...`). |
| GET | `/events` | Server-Sent Events stream of materialize lifecycle frames. |

The renderer is a static React build; in production it is served as
static files from the same FastAPI process via the optional
`--static-dir` flag. An Electron-based desktop build wraps the Viewer
for native use.

---

## 8. Exceptions

The reference implementation raises only typed exceptions from the
public surface. Every one extends `FolioError`.

<!-- spec-table: exceptions -->

| Class | Raised when |
|---|---|
| `FolioError` | Base class. Never raised directly. |
| `ContractError` | `contract.yaml` is malformed or violates §4. |
| `SheetError` | The sheet directory is missing or unreadable. |
| `RecordsError` | `records.jsonl` parse failure. |
| `QueryError` | DuckDB query fails or non-SELECT was attempted. |
| `OperationError` | A write violates record invariants (missing primary key, missing required field, etc.). |
| `PermissionDeniedError` | An actor does not match `x-editable-by` for a written field. Subclass of `OperationError`. |
| `LockTimeoutError` | The 30-second lock acquisition timed out. |
| `DerivationError` | A derivation file is malformed, depends cyclically, or fails to execute outside of a per-cell failure (which is reported on the envelope instead). |
| `SkillError` | A `skills/<name>.md` file is malformed (missing frontmatter, basename / name mismatch, undeclared argument placeholder, unknown tool name in the cross-checked allow-list, etc.). |

The Viewer maps each exception to an HTTP status code (400 for
contract / records / operation / query; 403 for permission-denied;
409 for lock-timeout; 422 for derivation; 500 fallback) and includes
the exception's `repr` in the JSON body.

---

## 9. Configuration

Environment variables and process-level flags Folio honors. Defaults
match what the bundled CLIs do today.

| Name | Surface | Effect |
|---|---|---|
| `FOLIO_CACHE_DIR` | SDK / CLI | Override `<user-cache>/folio` for this process. |
| `FOLIO_RUNTIME_DIR` | SDK / CLI | Override the per-sheet runtime root. |
| `ANTHROPIC_API_KEY` | `ai` derivations | Picked up by the default Anthropic-backed `AIClient`. |
| `LANG` | SDK | Hint for any future locale fallback. Not required today. |

CLI / API flags governing materialize behavior: `--force` (CLI;
`force=True` SDK / API) bypasses both the cache and the
`human_override` guard. `respect_human_override=false` on
`MaterializationConfig` (per-derivation, in YAML) bypasses only the
override guard.

The Viewer additionally reads:

- `--host` (defaults to `127.0.0.1`; do not change without a reason).
- `--port` (default `3000`).
- `--actor` (default actor used when an HTTP caller does not pass one).
- `--static-dir` (path to a pre-built frontend; defaults to
  `<repo>/viewer/dist` when present at the cwd).

---

## 10. Concept glossary

- **Sheet** — A directory matching §2.
- **Contract** — `contract.yaml`. Schema, identity, version.
- **Record** — One JSON object in `records.jsonl`. Identified by the
  primary key declared in the contract.
- **Derivation** — A YAML file under `derivations/` that fills one or
  more `x-derived` fields.
- **Target** — A field a derivation writes (`x-derived: true`).
- **Input** — A field whose value participates in `input_hash` for
  cache invalidation.
- **Actor** — Free-form string identifying who performed a write
  (`agent:human`, `agent:ops:reviewer`, …). Matched against
  `x-editable-by` patterns on every direct write.
- **Materialize** — Run all eligible derivations; skip cache hits and
  human overrides; append provenance; update records atomically.
- **Provenance** — `provenance.jsonl`. Append-only audit log per cell
  write.
- **Source** (in provenance) — One of `ai`, `import`, `python`, `sql`,
  `http`, `cross_sheet`, `human_override`. Determines override
  semantics on re-materialize (§5).
- **Materialization config** — Per-derivation YAML block:
  `materialization: { respect_human_override: bool }`.
- **`input_hash`** — `sha256:<hex>` over canonical inputs + derivation
  file + kind-specific extras (§3.4.9).

---

## 11. External references

- **Open Data Contract Standard (ODCS) v3.0.0** —
  <https://github.com/bitol-io/open-data-contract-standard>. The
  contract format in §3.1 is a subset; tools that read ODCS contracts
  (e.g. `datacontract-cli`) read Folio contracts unchanged.
- **JSON Lines (JSONL / `application/jsonl`)** —
  <https://jsonlines.org>. The records and provenance file formats.
- **Frictionless Data — Data Package** —
  <https://specs.frictionlessdata.io/data-package/>. `folio export
  datapackage` produces a Frictionless descriptor pointing at
  `records.jsonl`; the `logicalType` mapping in §3.1.4 lists the
  Frictionless-side names.
- **DuckDB** — <https://duckdb.org>. The query engine exposed by
  §3.2.5 (read-only; SELECT-only).
- **POSIX `fnmatch(3)` — pattern matching** — referenced by
  `x-editable-by` patterns (§3.1.3).
- **Model Context Protocol (MCP)** —
  <https://modelcontextprotocol.io>. The protocol the Folio MCP
  surface speaks (§7.3).
- **Server-Sent Events (`text/event-stream`)** —
  <https://html.spec.whatwg.org/multipage/server-sent-events.html>.
  The transport for the Viewer's lifecycle stream (`/events`).

---

## 12. Decision principles

The shape of this specification is a consequence of a small, fixed
set of design decisions:

- **ODCS subset for the contract.** The contract is readable by ODCS
  tooling unchanged; Folio adds only `x-`-prefixed extensions.
- **JSONL for records.** Streamable, grep-able, DuckDB-readable
  without ceremony.
- **DuckDB SELECT-only for queries.** Reads share the engine; writes
  go through the SDK so atomicity and provenance hold.
- **Single-writer `.lock`.** A 30-second `filelock` keeps multi-process
  semantics simple.
- **`fnmatch` for `x-editable-by`.** Familiar pattern syntax;
  case-sensitive matching against the actor string.
- **Cache and per-sheet runtime live outside the sheet.** A sheet is
  fully transportable as a tarball; nothing recoverable lives inside.

---

## 13. Verification

This specification is verified against the reference implementation
by a verifier script that lives alongside the source. When the
implementation evolves, the spec must be updated **before** the next
release; the verifier fails CI otherwise.

### 13.1 What is verified

The verifier parses the markdown tables marked
`<!-- spec-table: <id> -->` and asserts the live code agrees:

| Table id | Asserted against |
|---|---|
| `contract-fields` | `folio.contract.Contract.model_fields` (by alias) |
| `schema-fields` | `folio.contract.Schema.model_fields` (by alias) |
| `property-fields` | `folio.contract.Property.model_fields` (by alias) |
| `logical-types` | `folio.contract.LogicalType` literal values |
| `provenance-fields` | hand-curated set used by `Sheet.materialize` |
| `provenance-source` | `derivation.kind` enum + `human_override` |
| `derivation-base-fields` | `folio.derivation._BaseDerivation.model_fields` |
| `derivation-{kind}-fields` | each kind's Pydantic class |
| `readme-frontmatter` | `folio.readme.Frontmatter.model_fields` |
| `cli-verbs` | top-level commands of the Typer app at `folio.cli:app` |
| `sdk-methods` | public callable members of `folio.sheet.Sheet` |
| `mcp-tools` | tools registered on the FastMCP server |
| `viewer-routes` | FastAPI routes mounted by `folio_viewer.server.build_app` |
| `exceptions` | classes in `folio.exceptions` plus `DerivationError` |

### 13.2 Running the verifier

The verifier is invoked locally with:

```
python scripts/verify_spec.py
```

It exits non-zero on any drift and prints a summary listing missing,
extra, or mis-described fields. Tests and CI invoke the same script.
On success, no output is required.

### 13.3 Versioning

A material change to this document — new field, removed field,
renamed surface, semantic change — bumps the document's status line
and is accompanied by:

1. A code change that makes the verifier pass.
2. A release note in the repository changelog.

Backward-incompatible changes to the data format additionally bump
the major component of `apiVersion`.
