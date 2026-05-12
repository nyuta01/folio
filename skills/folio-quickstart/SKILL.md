---
name: folio-quickstart
description: >-
  Bootstrap a new Folio sheet from scratch — the contract.yaml schema,
  records.jsonl format, and the first materialize loop. Invoke when the
  user wants to start a Folio sheet, asks "how do I create a Folio
  data set", or has only data and needs a typed Folio container for it.
---

# Folio quickstart

Create a working Folio sheet (a directory containing `contract.yaml`
and `records.jsonl`) from a description of what data the user wants
to collect. Hand it back so other Folio skills (derivations,
materialize) can build on it.

## When this skill applies

- The user asks to "make a Folio sheet" / "set up Folio" / "build a
  data contract".
- The user has a CSV / JSON file and wants a typed, AI-friendly
  container for it.
- The user is starting a new entity collection (customers, research
  notes, support tickets, etc.) and wants the sheet to be the system
  of record.

This skill does **not** apply when the user already has a sheet and
wants to add a derivation, run materialize, or query — see the other
`add-derivation-*` and `debug-*` skills.

## Prerequisites

- `folio` Python CLI is installed:
  ```
  pipx install folio-kit   # or: uv tool install folio-kit
  ```
  (PyPI distribution name is `folio-kit`; the binary on disk is `folio`.)
  Verify with `folio --help`. If the user is on macOS Apple Silicon
  and `folio --help` errors with ENOENT, they may need to add
  `~/.local/bin` to PATH.

## Procedure

1. **Pick the slug.** Ask the user for a stable slug (kebab- or
   snake_case ASCII). Use it as both the directory name and the
   contract `id`. Example: `customers`, `research-notes`,
   `onboarding-queue`.

2. **Identify the primary key.** A Folio sheet must have *exactly
   one* `primaryKey: true` property. Composite keys are not allowed.
   When the data has no obvious key, generate one (`<slug>_<NNN>`).

3. **Identify required fields.** Anything the row cannot exist
   without. Mark them `required: true`.

4. **Pick `logicalType` per field.** The eight valid values are:
   `string`, `integer`, `number`, `boolean`, `date`, `timestamp`,
   `array`, `object`. Default to `string` when unsure.

5. **Write `contract.yaml`** at the sheet root. Skeleton:

   ```yaml
   apiVersion: v3.0.0
   kind: DataContract
   id: customers
   name: customers
   version: 1.0.0
   description: A customer master.
   schema:
     - name: items
       physicalType: jsonl
       properties:
         - name: id
           logicalType: string
           primaryKey: true
           required: true
         - name: company_name
           logicalType: string
           required: true
         - name: country
           logicalType: string
   ```

6. **Write `records.jsonl`** with one JSON object per line, no
   enclosing array. Every record must include the primary key.
   Skeleton:

   ```jsonl
   {"id": "cust_001", "company_name": "Acme", "country": "Japan"}
   {"id": "cust_002", "company_name": "DataFlow", "country": "United States"}
   ```

7. **Validate.** Always run `folio validate <sheet>` before handing
   the sheet back. Fix every error.

## Verify

```bash
folio validate <sheet>
folio list <sheet> --limit 3
```

Both should exit 0 and the second should print the records you
just wrote.

## What to do next

- For a derived field that an LLM fills, use the `add-derivation-ai`
  skill.
- For a 1:1 join to another sheet, use `add-derivation-cross-sheet`.
- For per-field write-permissions, set `x-editable-by` (an array of
  `fnmatch` patterns matched against the actor on every write).
- For external consumers, ship the sheet as a tarball — caches and
  per-sheet venvs live outside the directory and don't need to be
  bundled.

## Common mistakes (don't make them)

- **Two `primaryKey: true` properties.** `folio validate` rejects.
  Pick one.
- **`logicalType` outside the eight allowed values** (e.g. `text`,
  `int`, `datetime`). Map to the closest from the list.
- **Forgetting `apiVersion: v3.0.0`** or `kind: DataContract`. Both
  are required and pinned.
- **Putting the cache or venv inside the sheet.** Folio's cache
  lives at `<user-cache>/folio/<id>/cache/` by design — do not
  commit `.folio-cache/` directories.
