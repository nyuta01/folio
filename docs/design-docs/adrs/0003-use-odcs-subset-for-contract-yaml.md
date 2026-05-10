# ADR-0003 Use the ODCS Subset for contract.yaml

- **Status**: `accepted`
- **Date**: `2026-05-10`
- **Decision makers**: `agent`
- **Related**: `docs/design-docs/overview.md` §6, §14.1

## Context

A sheet's structure declaration (`contract.yaml`) needs a stable,
inspectable shape that AI agents and humans can both read, that external
tools can validate, and that does not lock Folio into a Folio-specific
schema language. The design overview §6 already names a subset of the
Open Data Contract Standard (ODCS) for this purpose, with extension
attributes (`x-derived`, `x-inputs`, `x-editable-by`) that follow the
ODCS / OpenAPI custom-extension convention.

Without an ADR, future implementations could drift toward Frictionless
Data Package, dbt model contracts, or a homegrown DSL.

## Decision

`contract.yaml` is a subset-compatible with ODCS:

- `apiVersion` is a full `vMAJOR.MINOR.PATCH` string referencing an
  actually-existing ODCS version (currently `v3.0.0`).
- `kind` is `DataContract`.
- `schema` is a single-element list (1 sheet = 1 model). Multi-model
  documents are out of scope; split into multiple sheets.
- Each property declares a `name`, a `logicalType` from the eight values
  listed in §6.3 (`string | integer | number | boolean | date |
  timestamp | array | object`), and optional `primaryKey`, `required`,
  `description`.
- Folio-specific extensions all use the `x-` prefix: `x-derived`,
  `x-inputs`, `x-editable-by`. Unknown property attributes are rejected
  by Pydantic.
- `description` is a string only in Phase 0. The future object form
  (`{ja: …, en: …}`) is an open issue.

`datapackage.json` for Frictionless Data Package interoperability is
optional and tracked separately for Phase 4.

## Consequences

- `contract.yaml` is validatable by external tools such as
  `datacontract-cli` without Folio-specific shims.
- The 1 sheet = 1 model invariant simplifies operation semantics (`list_records`,
  `query`, `get_record`) and matches `records.jsonl` being a single file.
- Folio extensions live in a clearly bounded namespace (`x-…`) so they
  can be ignored by ODCS consumers.
- Adding a logical type (e.g., `decimal`, `bytes`, `enum`) requires both
  a Pydantic model update and a corresponding ODCS mapping decision.

## Confirmation

`make python-test` exercises `tests/test_contract.py`, which covers
minimal valid contracts, invalid `logicalType` rejection, multiple-schema
rejection, multiple-primaryKey rejection, derived-input reachability,
duplicate-name rejection, and unknown-attribute rejection. Schema
invariants are also exercised end-to-end through `make cli-smoke`.

## Alternatives Considered

- Frictionless Data Package as the primary structure declaration. Its
  type vocabulary is broader, but it does not natively express
  derivations or extension attributes the way ODCS does. Kept as an
  optional output (Phase 4) rather than the primary format.
- A bespoke YAML schema. Lighter weight, but loses out on existing
  ODCS validators and tooling. Rejected.
