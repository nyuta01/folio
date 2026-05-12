# Folio: AI-Native Data Sheets

> Status: Draft v11 (named: Folio)
> Last updated: 2026-05-10
> Format version: 1
> Tagline: Portable, AI-native data sheets.
> Canonical path: `docs/design-docs/overview.md`

## Current implementation checkpoint (2026-05-10)

No product code exists yet. The repository contains the design document and
the AI-first engineering harness baseline (`FOLIO-H-001`). The next executable
slice is the [Phase 0 minimum sheet](../product-specs/phase-0-minimum-sheet.md).

This overview is the canonical product and technical design. Architecturally
significant decisions move into [`adrs/`](adrs/README.md) when they would
otherwise be rediscovered or re-debated by future agents.

## Three Design Priorities

This specification prioritizes the following three axes, in order:

1. **Simplicity**: Minimize the number of concepts. The minimum configuration is two files. Few rules to remember
2. **Portability**: Fully transportable via `tar`. No environment-dependent artifacts inside a sheet. Readable by external tools
3. **Generality**: Not tied to specific use cases or languages. Extension points are explicit

When these conflict, decisions follow the order **Simplicity > Portability > Generality**.

## Project Name and Terminology

**Folio** is the name of the entire project. It includes the CLI, SDK, Viewer, and other implementations.

The data unit at the specification level is **sheet** (1 directory = 1 sheet). This adopts terminology close to industry-common concepts (ODCS / dbt / Airtable). One folio handles one sheet.

Implementation package naming (reference):
- `folio` — Python SDK + CLI
- `folio-viewer` — Viewer

## Document Structure

- **Introduction** (§1-§4): Purpose, use cases, concepts, minimum configuration
- **Part 1: Sheet Specification** (§5-§14): Language-independent specification
- **Part 2: Python Reference Implementation** (§15-§20): The implementation provided by this project
- **Part 3: Implementation Plan** (§21-§23): Phase plan and samples
- **Appendix**: Open issues, references

Part 1 makes no assumption about Python. Part 2 is the Python implementation provided by this project.

---

# Introduction

## 1. Project Purpose

### 1.1 Problem to Solve

Situations where AI agents read and write structured data are rapidly increasing. But existing options are unsatisfying:

- **Spreadsheets**: Human-UI centric, inefficient for AI
- **Databases**: Hard to transport, heavy for lightweight tasks
- **Airtable / Notion DB**: SaaS lock-in, doesn't run locally
- **AI on top of Excel**: Bolt-on to existing grids; data model is not AI-native
- **Vector DB / RAG**: Semantic search infrastructure, not structured data management

What's missing is **"a data unit that AI agents can read and write as first-class users, that humans can later review and partially edit, that can be carried as files, and that is stable over the long term."** This project fills that gap.

### 1.2 Design Principles

1. **Easy for AI to operate**: Code execution + filesystem interface as the center
2. **Portable**: 1 directory = 1 unit. Self-contained via `tar`. Diffable via Git
3. **Interface-independent**: The specification doesn't depend on any interface. CLI / SDK / Viewer are thin wrappers
4. **Observable and reproducible**: Provenance for derived data, log for changes
5. **Progressive strictness**: Build up gradually from a minimum configuration
6. **Language-independent**: The Part 1 specification doesn't presuppose any specific language

### 1.3 Non-goals

- Real-time collaborative editing (CRDT)
- Pixel-level cell decoration, merged cells
- Full event sourcing
- Vector search / RAG
- Hundreds-of-millions record scale
- AI-specific features (AI is one of the derivation kinds)

### 1.4 Related Prior Art

| Axis | Reference | What we borrow |
|---|---|---|
| File + schema declaration | Frictionless Data Package | Standard schema representation |
| Data contract | Open Data Contract Standard (ODCS) | Vocabulary for contracts |
| Separation of declaration and implementation | dbt | Splitting schema from transform logic |
| Field as asset | Dagster Software-Defined Assets | Reconciliation idea |
| Agent interface | Anthropic Skills / code execution | File + code execution as center |
| Output format | TOON | Token-saving wire format |
| Derived field | Rowy Derivatives, Airtable formula | Derivation kind concept |

## 2. Use Cases

### 2.1 Customer Master Enrichment

Add metadata (industry, size, location) to company records that contain only name and URL. The sales agent populates records, AI fills derived fields, humans review weekly.

### 2.2 Structured Working Memory for Agents

A long-running research agent stores intermediate findings (candidates, verified facts) in a structured form. AI auto-attaches summaries and relevance scores.

### 2.3 Semi-structured Research Data Accumulation

Internal knowledge (research notes, competitive analysis, technical experiments) accumulates in category-specific sheets. AI fills tags, summaries, and categories.

### 2.4 Operational Worklist for Business Processes

Onboarding, contract renewal, and similar repetitive but not-fully-automatable processes are managed as a sheet. Some fields are updated by humans, others are auto-checked or filled by AI.

### 2.5 Common Properties

Shared characteristics across the four use cases:

- AI is a first-class user reading and writing
- Tens to hundreds of thousands of records
- Auto-update of derived fields is the core feature
- Portable as files
- Humans can engage later

These define the scope of this design. **Hundreds-of-millions-record analytics use cases and real-time multi-user editing are out of scope.**

## 3. Concepts

### 3.1 The Two Meanings of "AI-Native"

The term "AI-native" carries two interpretations in this specification:

1. **Generation side — derived fields**: Some cells are filled by AI
2. **Operation side — efficiency of operations**: Operations on the entire sheet are easy for AI agents

(2) has a larger impact on design. Agents are far more efficient when they operate the filesystem and run code than when they call many tools directly.

### 3.2 Conceptual Model: 2 Layers

```
   ┌──────────────────────────────────────┐
   │ Definition (low frequency)           │
   │   What is a field, how to fill it    │
   └──────────────┬───────────────────────┘
                  │ apply
                  ▼
   ┌──────────────────────────────────────┐
   │ Data (high frequency)                │
   │   Current values, provenance         │
   └──────────────────────────────────────┘
```

For simplicity, we use **2 layers**. Definition contains both "field declarations (contract)" and "derivation methods". Data is treatable as derived (recoverable by recomputation).

### 3.3 Terminology

| Term | Meaning |
|---|---|
| **sheet** | The unit defined by this specification. 1 directory = 1 sheet |
| **contract** | Declaration of a sheet's structure, semantics, and constraints |
| **field** | The column-equivalent unit |
| **record** | The row-equivalent unit |
| **logicalType** | The type of a field |
| **derivation** | Declaration of how to fill a derived field |
| **derivation kind** | The implementation method (`ai` / `import` / extensions) |
| **materialization** | The act of executing a derivation to fill records |
| **provenance** | Lineage info per record × field |
| **actor** | The performer of an operation (free-form string) |

Operation-side terms (SDK / CLI / Viewer) are defined in Part 2.

## 4. Overall Architecture

### 4.1 Minimum Configuration

The minimum sheet has two files:

```
my-sheet/
  contract.yaml         # Required: structure declaration
  records.jsonl         # Required: data (may be empty)
```

This is sufficient for a valid sheet. All other files are optional.

### 4.2 Configuration with Optional Features

```
my-sheet/
  contract.yaml          # Required
  records.jsonl          # Required
  README.md              # Optional: AI frontmatter + human-readable docs
  derivations/           # Optional: only when there are derived fields
    industry_tag.yaml
  scripts/               # Optional: reusable scripts
    enrich-industry.py
  attachments/           # Optional: binary attachments
  provenance.jsonl       # Optional: auto-generated when derivations run
  datapackage.json       # Optional: for external tool compatibility
  .lock                  # Internal: write lock
```

**Only items with persistent value live in the sheet directory.** Environment-dependent things like caches, logs, and venvs go outside (§13.3).

### 4.3 Interface Hierarchy

```
   ┌──────┐  ┌────────┐
   │ CLI  │  │ Viewer │  (any-language client)
   └───┬──┘  └────┬───┘
       └──────────┘
                  │
                  ▼ operates
       ┌──────────────────────┐
       │  Sheet directory     │
       │  (file group)        │
       └──────────────────────┘
```

The file layer is central; all interfaces read and write the same set of files. The Python SDK shown in Part 2 is **the first reference implementation** provided by this project, not a required component of the specification.

---

# Part 1: Sheet Specification

Part 1 is a **language-independent** specification. The Python implementation by this project is in Part 2.

## 5. File Layout

### 5.1 Required Files

- `contract.yaml`: Declaration of the sheet's structure and constraints
- `records.jsonl`: Record data (may be empty)

### 5.2 Optional Files

- `README.md`: Documentation. The leading YAML frontmatter can declare AI-oriented metadata
- `derivations/<field>.yaml`: Derivation method for a derived field
- `scripts/<name>.<ext>`: Reusable scripts (any language)
- `attachments/`: Binary attachments
- `provenance.jsonl`: Lineage of derived fields (auto-generated when derivations run)
- `datapackage.json`: Frictionless Data Package compatible descriptor

### 5.3 Internal Files

- `.lock`: Write lock (exists only during operations)

### 5.4 Items Not Placed in the Sheet Directory

- **Caches**: Computation caches go outside (§13.3)
- **venv**: Script execution environments go outside (§13.4)
- **Audit logs**: Exported externally as needed (§13.3)

This makes the size of `tar`-archived sheets purely proportional to the data.

### 5.5 Encoding

All text files are UTF-8, with LF line endings.

## 6. contract.yaml

### 6.1 Format

A subset-compatible with ODCS (Open Data Contract Standard).

```yaml
apiVersion: v3.0.0
kind: DataContract
id: customers
name: customers
version: 1.0.0
description: Customer master

schema:
  - name: customers
    physicalType: jsonl
    properties:
      - name: id
        logicalType: string
        primaryKey: true
        required: true
        description: Immutable customer ID

      - name: company_name
        logicalType: string
        required: true
        description: Official company name

      - name: industry_tag
        logicalType: string
        description: A single-word industry tag
        x-derived: true
        x-inputs: [company_name]
```

`apiVersion` is specified in full (major.minor.patch) using an actually-existing ODCS version. Shorthand like `v3` is not used because standard ODCS validators don't accept it.

### 6.2 1 Sheet = 1 Model

ODCS's `schema` is an array, but in this specification **only one element is allowed**. To handle multiple data structures, split into multiple sheets.

This is because:
- records.jsonl is a single file
- It simplifies operation semantics
- A workspace concept that bundles multiple sheets is for future consideration (open issue)

### 6.3 Supported logicalType

| logicalType | JSON representation |
|---|---|
| `string` | `"foo"` |
| `integer` | `42` |
| `number` | `3.14` |
| `boolean` | `true` / `false` |
| `date` | `"2026-05-09"` (ISO 8601 date) |
| `timestamp` | `"2026-05-09T10:00:00Z"` (RFC 3339) |
| `array` | `[...]` |
| `object` | `{...}` |

All types allow null (forbidden by `required: true`).

### 6.4 Extension Attributes (x- prefix)

- `x-derived: true`: This field is a derived field (a corresponding `derivations/<name>.yaml` exists)
- `x-inputs: [...]`: List of upstream fields used in derivation (lineage)
- `x-editable-by: [...]`: Edit permissions (optional, see §9)

Attributes starting with `x-` follow the ODCS / OpenAPI convention for custom extensions.

### 6.5 Multilingual descriptions

In Phase 0, `description` supports **string only** (prioritizing ODCS standard compliance).

A future extension may allow object form:

```yaml
description: Industry tag                     # Phase 0: string only
description:                                  # Future
  ja: 業種タグ
  en: Industry tag
```

When introducing the object form, ODCS compatibility (passing `datacontract-cli`) and the default-language selection logic must be defined (open issue).

### 6.6 Constraint Validation

- `primaryKey: true` field: At most one per model. Same value across records is treated as update
- `required: true`: For non-derived fields, null is rejected at upsert time. For derived fields, null is allowed before materialize

### 6.7 Lifecycle

`version` in contract.yaml is managed as semver. For breaking changes, a migrator script is included in `migrations/` (operationally finalized).

## 7. records.jsonl

A simple JSON Lines file with values only.

```jsonl
{"id":"cust_001","company_name":"Acme Inc","industry_tag":"Manufacturing"}
{"id":"cust_002","company_name":"DataFlow","industry_tag":null}
```

Reasons for not using a wrapper structure:
- External tools (jq, DuckDB, pandas) handle it naturally
- Record sizes don't bloat
- Lineage information lives in a separate file (provenance.jsonl)

An empty file (0 records) is also a valid sheet.

## 8. derivations/

### 8.1 Format

One file per derived field at `derivations/<field_name>.yaml`. The `kind` field selects the implementation method.

### 8.2 Standard Kinds

The standard kinds defined in this specification are **`ai` and `import`**. Other kinds are treated as extensions (§8.5).

#### ai kind

```yaml
targets: [industry_tag]        # Output fields (always an array, even when single)
inputs: [company_name]         # Input fields
kind: ai
model: <model_id>              # e.g., claude-sonnet-4-6
prompt: |
  Answer with a single English word that describes the industry of
  the following company.

  Company: {{ company_name }}

  Reply with only the word, no explanation.
output: text                   # text | json
```

`targets` is always an array. Even with a single output field, write `[industry_tag]`. This keeps consistency and avoids implementations needing to branch on single-vs-multiple cases.

The prompt is **written inline**. For longer prompts, `prompt_ref: prompts/industry_tag.md` is also supported (both forms accepted).

Template expansion supports only `{{ field_name }}` form (a subset of Mustache / Jinja2). This avoids tying the spec to any particular language.

#### Output, targets, and output_schema

| Number of targets | output | output_schema |
|---|---|---|
| 1 | `text` (for string-typed fields) | not needed |
| 1 | `json` (for object/array-typed fields) | not needed (determined by the field's logicalType) |
| 2 or more | `json` (required) | required (declares the type of each target) |

#### Multiple targets

When you want one AI call to fill multiple fields:

```yaml
targets: [industry_tag, employee_size, headquarters_country]
inputs: [company_name, company_url]
kind: ai
model: <model_id>
prompt: |
  For the following company, return its industry, employee size, and
  headquarters country.

  Company: {{ company_name }}
  URL: {{ company_url }}
output: json
output_schema:
  industry_tag: string
  employee_size: string
  headquarters_country: string
```

This avoids a 3x cost increase.

#### import kind

Pull values from external files or command output.

```yaml
targets: [legacy_id]
inputs: []
kind: import
source: legacy/customer_mapping.csv
key_field: id
value_field: legacy_customer_id
```

### 8.3 Stale Detection

A derived field of a record is stale when:

```
The latest provenance.input_hash for that record × field
  ≠
The currently computed input_hash
```

`input_hash` calculation rules are in §11. Because file content hashes are part of it, editing a derivation or prompt automatically marks records as stale.

### 8.4 Dependency Resolution Among Derivations

When a derived field uses another derived field as input, materialize is executed in dependency order.

Implementation:
1. Read all derivations and build a target → inputs DAG
2. Topologically sort the materialize targets
3. Cycles are an error (also checked at validate time)

### 8.5 Extension Kinds

Implementations may support arbitrary kinds via `kind: <name>`. The spec defines `ai` and `import`.

Representative extensions (also provided by this project's reference implementation):
- `sql`: DuckDB SQL expression
- `http`: HTTP API call
- `python`: Call a function in `scripts/`
- `cross_sheet`: Derive from another sheet's records

YAML structure for extension kinds is outside the specification's scope. Implementations define them.

### 8.6 Materialization Control

```yaml
materialization:
  trigger: on_demand            # The only supported value in this version
  respect_human_override: true  # Whether to respect human overrides
```

`on_demand` means "becomes a stale-detection target when the `materialize` operation is called." Auto-triggers (`on_upstream_change`, etc.) are for future consideration.

## 9. provenance.jsonl

An append-only file auto-generated when derivations run. No need to write to it manually.

### 9.1 Schema

```jsonl
{"record_id":"cust_001","field":"industry_tag","source":"ai","actor":"agent:enrichment-bot","at":"2026-05-09T10:00:00Z","input_hash":"sha256:abc...","model":"<model_id>","cost_usd":0.0008}
{"record_id":"cust_002","field":"industry_tag","source":"human_override","actor":"alice@example.com","at":"2026-05-09T11:00:00Z"}
```

| Field | Required? | Description |
|---|---|---|
| `record_id` | Required | Primary key of the target record |
| `field` | Required | Target field name |
| `source` | Required | `ai` / `import` / `human_override` / extension kind name |
| `actor` | Required | Performer of the operation (free-form string) |
| `at` | Required | RFC 3339 timestamp |
| `input_hash` | Required when source is a derivation | Cache key (§11) |
| Other | Optional | Kind-specific info (model, cost_usd, etc.) |

The latest provenance is resolved on the read side (last entry for `(record_id, field)` from append-only).

### 9.2 actor

`actor` is a **free-form string**. The spec does not enforce a regex. Conventions:

- `agent:<name>`: AI agent
- `human:<id>` or email: Human
- `system`: Internal processing

Implementations decide operational rules. This makes integration with auth systems (JWT subject, OAuth identifier) flexible.

### 9.3 Edit Permissions

`x-editable-by` is **optional**. Without it, anyone can edit. With it, interpretation is up to the implementation (pattern-match against actor strings).

Example:

```yaml
x-editable-by:
  - "agent:*"          # any agent
  - "human:alice"       # specific human
```

This keeps the permission model minimal while leaving room for extension. Real auth/authz is built by the implementation.

## 10. Operation Semantics

This defines the semantics of operations on a sheet. Interfaces (CLI / Viewer / SDK) implement these.

### 10.1 Design Approach

- **Minimal core operations**: Only specify the necessary verbs
- **Common filter syntax**: Same expression across all read operations
- **Aggregation via SQL**: No aggregation operations in core; instead, a `query` operation
- **Writes require actor**: To preserve lineage

### 10.2 Core Operations

| Operation | Meaning |
|---|---|
| `get_contract()` | Returns the contract |
| `query(sql, params?)` | Execute DuckDB SQL (against records.jsonl) |
| `list_records(filter?, fields?, limit?, cursor?, format?)` | Fetch records |
| `get_record(id, fields?)` | Single record |
| `upsert_records(records, actor)` | Insert or update |
| `delete_records(ids, actor)` | Delete |
| `materialize(targets?, record_ids?, force?, actor)` | Execute derivations |
| `materialization_status(targets?)` | Status of derivations |
| `provenance(record_id, field, history?)` | Lineage (with `history` for full history) |

**9 operations** (down from 13 in v8). Aggregation operations (count_records, stats, distinct_values, group_by) are subsumed by `query`.

### 10.3 query operation

```
query(sql: str, params?: list) → list[dict]
```

Executes DuckDB SQL against records.jsonl. The table name `records` is available.

**Read-only and sandbox constraint**: `query` only allows SELECT-style queries. INSERT / UPDATE / DELETE / CREATE / DROP and similar are rejected. Writes use `upsert_records` / `delete_records`. The query engine must also be filesystem-sandboxed: caller SQL can see only the in-memory `records` relation that Folio constructs from `records.jsonl`, not arbitrary local files through DuckDB table functions such as `read_text`, `read_csv_auto`, `read_json`, or `glob`. The Python reference implementation enforces this by loading `records.jsonl` through Python, inserting it into a temporary DuckDB table, and opening DuckDB with external access disabled.

Examples:
```sql
-- Count (alias recommended)
SELECT COUNT(*) AS count FROM records WHERE industry_tag IS NULL;

-- Distribution
SELECT industry_tag, COUNT(*) AS n FROM records GROUP BY 1 ORDER BY 2 DESC;

-- Stats
SELECT MIN(created_at) AS min_at, MAX(created_at) AS max_at, COUNT(DISTINCT industry_tag) AS distinct_industries FROM records;
```

Aliases (e.g., `AS count`) are recommended. Without aliases, DuckDB returns auto-generated names like `count_star()`, which makes results harder to read.

This makes aggregation and analysis very general. Convenience helpers (`stats`, `count`, etc.) are provided as SDK wrappers (not required by the spec).

### 10.4 Filter Syntax

The `filter` parameter of `list_records` is a **string valid as a DuckDB WHERE clause**.

```python
filter = "industry_tag IS NULL"
filter = "industry_tag IN ('Manufacturing', 'IT')"
filter = "company_name LIKE '%Inc%' AND industry_tag IS NULL"
```

This eliminates the need for a custom AST and lets users use their existing SQL knowledge. To prevent SQL injection, user-provided values pass through `params`:

```python
list_records(filter="industry_tag = ?", params=["Manufacturing"])
```

### 10.5 list_records Return Value

```
{
  "records": [...] or string (TOON),
  "format": "json" | "toon",
  "limit": int,
  "next_cursor": string | null
}
```

`format` may be `json` (default) or `toon` (token-efficient wire format).

### 10.6 materialize Return Value

```
{
  "materialized": int,
  "skipped": int,           # not stale or human_override
  "failures": [{"record_id": ..., "field": ..., "error": ..., "error_type": ...}],
  "total_cost": number      # depends on kind (USD, etc.)
}
```

### 10.7 Design Principles

1. **Writes require `actor`**
2. **Reads default to a small `limit`** (e.g., 50)
3. **Aggregation via `query()`** (or SDK convenience functions)
4. **Don't grow the operation count**: Convenience verbs become SDK syntactic sugar, not part of the spec

### 10.8 Updating the Contract

`update_contract` is **not** specified as an operation. Users edit `contract.yaml` directly. If programmatic updates become necessary, an extension may be introduced (open issue).

## 11. Cache Key

Computed results of derived fields are cached using a content-addressed key:

```
input_hash = sha256(canonical_json({
  derivation_file_hash: <SHA-256 of derivations/<name>.yaml>,
  prompt_file_hash:     <SHA-256 of prompt body>,  # only for ai kind
  model:                <model ID from derivation>, # only for ai kind
  inputs:               { <input_field>: <input_value>, ... }
}))
```

`canonical_json` follows **RFC 8785 (JCS, JSON Canonicalization Scheme)**.

Because file content hashes are part of the cache key, editing a file automatically causes a cache miss. Explicit version numbers are not needed.

When the prompt is inline, `prompt_file_hash` uses the SHA-256 of the inline content.

The physical location of the cache is up to the implementation (§13).

## 12. Concurrency and Locking

Single-writer assumption:

- Acquire the `.lock` file directly under the sheet before writing
- Default lock acquisition timeout is 30 seconds (adjustable by implementation)
- Lock is write-only. Reads can be concurrent
- Concurrent writes from multiple agents are serialized by an upstream queue
- CRDT is not introduced

Atomicity of writes:
- Updates to `records.jsonl`: temp file + rename
- Appends to `provenance.jsonl`: OS-level atomic append (size ≤ PIPE_BUF)

## 13. Placement of Environment-Dependent Items

### 13.1 Items Placed Inside the Sheet

Only artifacts that constitute the sheet itself:
- contract.yaml
- records.jsonl
- README.md (optional)
- derivations/ (optional)
- scripts/ (optional)
- attachments/ (optional)
- provenance.jsonl (optional)
- datapackage.json (optional)

### 13.2 Items Not Placed Inside the Sheet

These live outside because they are environment-dependent or grow large:

#### Computation cache

Placed under `<user-cache>/<sheet-id>/cache/`. Examples:

- Linux: `~/.cache/folio/<sheet-id>/cache/`
- macOS: `~/Library/Caches/folio/<sheet-id>/cache/`
- Windows: `%LOCALAPPDATA%\folio\<sheet-id>\cache\`

`<sheet-id>` uses the `id` from `contract.yaml`.

#### Script execution environment

Execution environments for `scripts/` (Python venv, Node.js node_modules, etc.) live outside:

- `<user-cache>/<sheet-id>/runtime/`

A script is just "a file to be executed"; the environment is prepared by the implementation.

#### Audit logs

If detailed logs are needed, the implementation outputs them externally. Not retained inside the sheet.

### 13.3 As a Result, `tar` Size Is Proportional to Data

When archived via `tar czf customers.sheet.tgz customers/`, only canonical files are included. The receiver rebuilds caches and venvs from scratch.

This is the essence of portability.

### 13.4 Script Languages Are Not Fixed by the Spec

File extensions and execution languages under `scripts/` are free. Python (`*.py`), Node.js (`*.js`), shell (`*.sh`), anything is allowed. Implementations may declare the language used in a particular sheet via README.md frontmatter.

This keeps the spec from being tied to any particular language.

## 14. Standard Compatibility

### 14.1 ODCS

`contract.yaml` is a subset-compatible with ODCS. Validatable via tools like `datacontract-cli`.

### 14.2 Frictionless Data Package

`datapackage.json` is optionally generated. Frictionless-compatible tools (`frictionless` Python library, etc.) can read the data part. This makes a sheet **"a portable data package with type information"**.

Mapping for generation:

| ODCS | Frictionless |
|---|---|
| `schema[].name` | `resources[].name` |
| `schema[].properties[].name` | `resources[].schema.fields[].name` |
| `schema[].properties[].logicalType` | `resources[].schema.fields[].type` (mapping table needed) |
| `schema[].properties[].description` | `resources[].schema.fields[].description` |
| `schema[].properties[].primaryKey` | aggregated to `resources[].schema.primaryKey` |

Detailed mapping is finalized in Phase 4.

### 14.3 Out of Scope

- **Parquet / Iceberg / Delta**: Columnar formats are at odds with this spec's premise (directly editable JSONL). For scale, redesign as a separate sheet spec
- **CRDT**: Collaborative editing is not in scope
- **Vector / RAG**: External systems

---

# Part 2: Python Reference Implementation

This is the **first reference implementation** provided by this project, written in Python. The specification welcomes implementations in other languages.

## 15. Interfaces

```
   ┌──────┐  ┌────────┐
   │ CLI  │  │ Viewer │
   └───┬──┘  └────┬───┘
       └──────────┘
                   │
                   ▼
              SDK (Python)
                   │
                   ▼
         Sheet directory
```

CLI and Viewer access files through the SDK. The SDK exposes operations as Python methods.

## 16. SDK Overview

```python
import folio

s = folio.open(".", actor="agent:enrichment")

# contract
s.contract                              # Contract dict

# query (the main verb)
s.query("SELECT COUNT(*) FROM records WHERE industry_tag IS NULL")

# Aggregation convenience wrappers (syntactic sugar for query)
s.records.count()
s.records.stats("created_at")           # min/max/null/distinct for numeric and date
s.records.distinct("industry_tag")
s.records.group_by("industry_tag")

# Record operations
s.records.where("industry_tag IS NULL").limit(10).to_list()
s.records.where("industry_tag IS NULL").limit(10).to_jsonl()
s.records.where("industry_tag IS NULL").limit(10).to_toon()
s.records.get("cust_001")
s.upsert([{"id": "cust_003", ...}])     # actor is context-bound

# materialize
s.materialize("industry_tag")
s.materialize("industry_tag", force=True)
s.status("industry_tag")

# provenance
s.provenance("cust_001", "industry_tag")
s.provenance("cust_001", "industry_tag", history=True)
```

The aggregation convenience wrappers (`count`, `stats`, `distinct`, `group_by`) are provided by the SDK as syntactic sugar. Internally they just call `query()`. They are not part of the spec.

## 17. CLI

A thin wrapper over the SDK using Typer. The executable is `folio`.

```bash
folio validate <sheet>                       # Validate contract and derivations
folio query <sheet> "<sql>"                  # Execute DuckDB SQL
folio count <sheet> [--filter <expr>]
folio stats <sheet> <field> [--filter <expr>]
folio list <sheet> [--filter <expr>] [--fields <list>] [--format json|toon] [--limit N]
folio upsert <sheet> --file <path> --actor <a>
folio delete <sheet> --ids <list> --actor <a>
folio materialize <sheet> [<field>] [--force] [--ids <list>] --actor <a>
folio status <sheet> [<field>]
folio provenance <sheet> <record_id> <field> [--history]
folio serve <sheet> [--port 3000]            # Viewer server
```

`<sheet>` is a path to a sheet directory. The `--filter` value is a SQL WHERE-clause string.

## 18. Agent Interfaces

Agents operate Folio through the CLI and sheet-local skills. The project does
not ship a network tool server; removing that surface keeps Folio aligned with
the local, inspectable, file-first trust model. Remote orchestration should use
explicit application code on top of the SDK rather than exposing a generic
unauthenticated sheet tool surface.

## 19. Viewer

### 19.1 Architecture

- Backend: FastAPI directly imports the SDK
- Frontend: React + TanStack Table + TanStack Virtual
- Communication: REST (primary) + SSE (one-way push for agent activity)
- Bind: 127.0.0.1 only, CSRF token required
- Desktop coding-agent runs are Electron-main-process only and must derive
  their working directory from the currently opened sheet tracked by the main
  process, never from renderer-provided IPC payload fields.

### 19.2 Roles

Does: visualize contract and records, edit fields with `editable_by`, hover provenance, show materialization status, observe agent activity

Does not: edit contract / derivations (edit files directly), real-time collaborative editing

### 19.3 Stages

| Stage | Feature |
|---|---|
| V0 | Read-only display of records.jsonl |
| V1 | Show types and descriptions from contract |
| V2 | Edit human-editable fields |
| V3 | Provenance hover, derivation badges, status colors |
| V4 | Materialize dashboard |
| V5 | History view |
| V6 | Live agent activity via SSE |

### 19.4 REST Endpoints

One-to-one mapping with operations. Details finalized in Phase 5.

## 20. Library Selection

| Purpose | Choice |
|---|---|
| Validation | Pydantic v2 |
| YAML | PyYAML |
| Data manipulation | DuckDB |
| AI calls | anthropic SDK |
| Lock | filelock |
| Canonical JSON | rfc8785 |
| CLI | Typer |
| Prompt template | self-implemented (`{{ field }}` only) |
| HTTP | httpx (for http kind) |
| Viewer backend | FastAPI |
| Viewer frontend | React + TanStack Table + TanStack Virtual |
| TOON encoding | self-implemented (thin) |
| Validation tools | datacontract-cli, frictionless |

### 20.1 Rationale for Python

The industry trend is bifurcated:
- Coding agent runtimes (Claude Code, etc.) → TypeScript
- Skills / scripts called by agents (Anthropic's official docx/xlsx/pdf/pptx skills) → Python

This design follows the latter pattern. Aligning with Anthropic's production examples and the default execution environment of the official code_execution tool (Python + bash). The Viewer frontend uses React/TS.

---

# Part 3: Implementation Plan

## 21. Phase Plan

| Phase | Scope |
|---|---|
| 0 | contract.yaml + records.jsonl + core operations + CLI |
| 1 | derivations/ (ai/import kind) + provenance + cache |
| 2 | scripts/ + README frontmatter (AI metadata) |
| 3 | TOON output |
| 4 | Extension kinds (sql/http/python) + datapackage.json generation |
| 5 | Viewer |
| 6 | Multi-sheet integration |
| 7 (future) | Multi-user, Tauri-fication, workspace concept |

Each phase preserves the compatibility of Part 1's specification (including operations).

## 22. Phase 0 Scope

### 22.1 The Real Minimum

The minimum sheet should run:

```
my-sheet/
  contract.yaml      # Valid even with one field
  records.jsonl      # Valid even when empty
```

`folio validate` recognizes this configuration as valid.

### 22.2 Features to Implement

- contract.yaml validation via Pydantic v2
- records.jsonl reading via DuckDB
- `validate` CLI command
- Operations:
  - `get_contract()`
  - `query(sql, params)`
  - `list_records(filter, fields, limit, cursor)` — format is json only
  - `get_record(id, fields)`
  - `upsert_records(records, actor)`
  - `delete_records(ids, actor)`
- editable_by validation (only if specified)
- Write lock via `.lock`
- Atomic writes via temp file + rename
- CLI: `validate / query / list / count / upsert / delete`

### 22.3 Items Not Implemented in Phase 0

- derivation
- materialization
- provenance (no derivation execution, so it doesn't occur)
- cache
- TOON output (json only)
- Viewer
- scripts/
- Extension kinds

## 23. Sample Sheets

### 23.1 Minimum Sample

```
minimal-sheet/
├── contract.yaml
└── records.jsonl
```

`contract.yaml`:
```yaml
apiVersion: v3.0.0
kind: DataContract
id: minimal
name: minimal
version: 1.0.0
schema:
  - name: items
    physicalType: jsonl
    properties:
      - name: id
        logicalType: string
        primaryKey: true
        required: true
      - name: name
        logicalType: string
        required: true
```

`records.jsonl` (may be empty):
```jsonl
{"id":"item_001","name":"first"}
```

This alone makes `folio validate`, `folio list`, and `folio upsert` work.

### 23.2 Phase 1 Completion Sample

A complete customer enrichment sheet:

```
customers/
├── README.md
├── contract.yaml
├── derivations/
│   └── industry_tag.yaml
├── records.jsonl
└── provenance.jsonl    # auto-generated after materialize
```

`contract.yaml`:
```yaml
apiVersion: v3.0.0
kind: DataContract
id: customers
name: customers
version: 1.0.0
description: Customer master. Sales agents collect, humans review.

schema:
  - name: customers
    physicalType: jsonl
    properties:
      - name: id
        logicalType: string
        primaryKey: true
        required: true

      - name: company_name
        logicalType: string
        required: true
        x-editable-by: ["agent:*", "human:*"]

      - name: company_url
        logicalType: string
        x-editable-by: ["agent:*", "human:*"]

      - name: industry_tag
        logicalType: string
        description: A single-word industry tag
        x-derived: true
        x-inputs: [company_name]
        x-editable-by: ["agent:enrichment-bot", "human:*"]
```

`derivations/industry_tag.yaml`:
```yaml
targets: [industry_tag]
inputs: [company_name]
kind: ai
model: claude-sonnet-4-6
prompt: |
  Answer with a single English word that describes the industry of
  the following company.

  Company: {{ company_name }}

  Reply with only the word, no explanation.
output: text
materialization:
  trigger: on_demand
  respect_human_override: true
```

`records.jsonl`:
```jsonl
{"id":"cust_001","company_name":"Acme Manufacturing Inc","company_url":"https://acme.example.com","industry_tag":"Manufacturing"}
{"id":"cust_002","company_name":"DataFlow Technologies","company_url":"https://dataflow.example.com","industry_tag":null}
{"id":"cust_003","company_name":"Green Farm Co.","company_url":null,"industry_tag":null}
```

### 23.3 Phase 1 Completion Scenario

```bash
# 1. validate
$ folio validate ./customers
✓ contract.yaml is valid
✓ derivations/industry_tag.yaml is valid
✓ All records conform to schema

# 2. Check records without industry
$ folio query ./customers "SELECT COUNT(*) AS n FROM records WHERE industry_tag IS NULL"
[{"n": 2}]

# 3. Fill industries via AI
$ folio materialize ./customers industry_tag --actor "agent:enrichment-bot"
Materializing industry_tag for 2 records...
✓ cust_002: Software (cost: $0.0008)
✓ cust_003: Agriculture (cost: $0.0009)
Total: 2 materialized, 0 skipped, 0 failed, $0.0017

# 4. Distribution
$ folio query ./customers "SELECT industry_tag, COUNT(*) AS n FROM records GROUP BY 1"
[{"industry_tag":"Manufacturing","n":1},{"industry_tag":"Software","n":1},{"industry_tag":"Agriculture","n":1}]

# 5. Human override
$ folio upsert ./customers --file - --actor "human:alice" <<EOF
{"id":"cust_003","industry_tag":"AgTech"}
EOF
1 updated

# 6. provenance
$ folio provenance ./customers cust_003 industry_tag --history
[
  {"source":"ai","actor":"agent:enrichment-bot","at":"2026-05-09T10:05:00Z",...},
  {"source":"human_override","actor":"human:alice","at":"2026-05-09T11:00:00Z",...}
]
```

If this scenario runs, Phase 1 is complete.

---

# Appendix

## Appendix A. Major Changes

### v10 → v11 (naming decision)

- Project named **Folio**
- CLI command renamed `sheet` → `folio`
- Python package renamed `sheet` → `folio`
- The data unit term "sheet" remains as a spec-level concept

### v9 → v10 (final review applied)

- Fixed apiVersion to `v3.0.0` (`v3` is not accepted by ODCS validators)
- Unified `target` / `targets` to `targets` array (always array, for simplicity and consistency)
- Made the query operation read-only (SELECT only; writes use upsert/delete)
- Restricted description to string in Phase 0 (multilingual is future)
- Recommended `AS` aliases in scenarios
- Added an output / targets / output_schema correspondence table
- Added 7 unresolved points to open issues

### v8 → v9 (redesigned for simplicity / portability / generality)

#### Simplification

- Conceptual model: 3 layers → **2 layers** (Definition / Data)
- Operations: 13 → **9**. Aggregations subsumed by `query`
- Filter: custom AST → **DuckDB SQL string**
- Prompts: **inline within derivation YAML** (external file reference also allowed)
- Merged SKILL.md into README.md (AI metadata via YAML frontmatter)
- Minimum configuration: `contract.yaml + records.jsonl` (**2 files**)

#### Portability improvements

- `.cache/` moved **outside the sheet** (user cache)
- `.history/` removed from the sheet (export externally if needed)
- `scripts/.venv/` moved **outside the sheet**
- Sized of `tar`-archived sheets is purely proportional to data

#### Generality improvements

- Allowed **derivation targets to be an array** (multiple fields per AI call)
- Made derivation kinds **pluggable**. Standards: `ai` / `import` only; others are extensions
- Limited prompt templates to **`{{ field }}` only** (language-independent, subset of Jinja2 / Mustache)
- Made description **multilingual-capable**
- Made actor a **free-form string** (room for auth integration)
- **Did not fix the language of scripts/** in the spec

#### Removed constraints

- SKILL.md required → merged into README.md (optional)
- scripts/requirements.txt required → up to the implementation
- scripts venv from Phase 0 → moved to Phase 2+
- Excessive implementation details (env var values, retry numbers, etc.)

## Appendix B. Open Issues

### Spec-level

- **Workspace concept that bundles multiple sheets**: Currently sheets have no relationships
- **Inter-sheet relationships**: Foreign key representation
- **Criteria for promoting `update_contract` to an operation**
- **Multilingual description selection logic**: When introducing object form, decide between env / config / argument
- **Standardization of extension kinds**: YAML structure for sql / http / python, and plug-in points for third-party kinds
- **SDK behavior on derivation failure**: How far to spec partial failures (multi-line return for `output: text`, invalid JSON for `output: json`, etc.); currently left to the implementation
- **README.md frontmatter convention**: Required and optional fields for AI metadata, alignment with Anthropic Agent Skills SKILL.md convention
- **sheet-id collision avoidance**: Cache-collision countermeasures when different sheets share the same `id` in contract.yaml (add path-hash to the identifier?)
- **Meaning of provenance `at`**: materialize start / API call end / records.jsonl write — which timestamp to record
- **Atomicity of materialize**: Handling intermediate state when killed mid-way through a large materialize, checkpoint strategy
- **Relationship between delete_records and cache**: How to handle provenance / cache for deleted records
- **Operation / CLI naming alignment**: Document the mapping between `materialization_status` operation and `folio status` CLI

### Implementation-level

- **AI retry strategy values** (Phase 1)
- **scripts isolated environment setup timing** (Phase 2)
- **TOON encoder spec details** (Phase 3)
- **ODCS↔Frictionless mapping details** (Phase 4)
- **Viewer desktop-ification** (Tauri, future)
- **Multi-user hosting** (future)

### Out of scope

- Parquet / Iceberg / Delta (separate sheet spec)
- CRDT-based collaborative editing
- Vector search / RAG
- Multiple models per sheet

## Appendix C. References

### Standards

- Open Data Contract Standard (ODCS): https://bitol.io/
- Frictionless Data Package: https://specs.frictionlessdata.io/
- OpenLineage: https://openlineage.io/
- Agent Skills: https://agentskills.io/
- TOON: https://github.com/toon-format/toon
- RFC 8785 JSON Canonicalization Scheme: https://datatracker.ietf.org/doc/html/rfc8785

### Concepts and Patterns

- dbt model contracts
- Dagster Software-Defined Assets
- DVC content-addressed storage
- Rowy Derivatives field type
- Airtable Formula / AI field
- Anthropic Skills repository: https://github.com/anthropics/skills
- Anthropic "Writing effective tools for agents"

### Libraries

- Pydantic v2: https://docs.pydantic.dev/
- DuckDB: https://duckdb.org/
- Typer: https://typer.tiangolo.com/
- filelock: https://pypi.org/project/filelock/
- FastAPI: https://fastapi.tiangolo.com/
- TanStack Table / Virtual: https://tanstack.com/
- rfc8785: https://pypi.org/project/rfc8785/

### Validation Tools

- datacontract-cli: https://cli.datacontract.com/
- frictionless-py: https://framework.frictionlessdata.io/
