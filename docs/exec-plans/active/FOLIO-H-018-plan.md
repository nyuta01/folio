# FOLIO-H-018 Plan: TOON Output

## Goal

Add a thin, deterministic TOON encoder for `list_records` so callers
can request a token-efficient wire format instead of JSON, matching
§10.5 of the design overview and §20's "self-implemented (thin)"
library selection.

## Scope

- `src/folio/_toon.py`:
  - `encode(records: list[dict]) -> str` returning a header line
    (`[N]{field1, field2, ...}`) followed by one body line per
    record. Each body cell is JSON-encoded for non-trivial values
    (objects, arrays, strings with commas / quotes / whitespace);
    "trivial" scalars (plain identifiers, numbers, booleans, null)
    pass through unquoted for the token-efficiency that the format
    name promises.
  - `EMPTY_TOON_HEADER` constant for the empty-list case
    (`[0]{}:`).
  - Public re-exports from `folio.__init__`.
- `Sheet.list_records(..., format="json" | "toon")`. The default
  remains `"json"`. When `format == "toon"`, the `records` key in
  the envelope is a TOON string; the envelope still reports
  `format: "toon"`, `limit`, and `next_cursor` per §10.5.
- `folio list <sheet> --format json|toon` CLI option threaded
  through.
- `tests/test_toon.py` covering: empty list, scalar-only records,
  string with comma / quote / leading-or-trailing whitespace,
  null / boolean / int / float passthrough, nested object /
  nested array values, deterministic field ordering (header order
  matches the union of keys across records, sorted), and the
  `Sheet.list_records(format="toon")` integration.
- `tests/test_cli.py` extension for `--format toon`.
- `scripts/harness_check.py` requires the new module and tests.

## Out of scope

- Full conformance with the upstream toon-format/toon
  specification. The design overview §20 calls for a thin
  self-implementation; future alignment can promote behavior to a
  shared TOON ADR.
- A TOON decoder. Round-trip is asserted by hand-coded expected
  strings; agents that consume TOON do so as opaque text.
- TOON output for `query`, `get_record`, or `materialize` envelopes.
  Phase 3 limits the format option to `list_records` per the
  design overview.

## Evidence

- `make verify` passes with the new pytest cases.
- `folio list <sheet> --format toon` prints the envelope with a
  TOON `records` string.

## Observation

The Phase 1 `list_records` envelope already advertises `format:
"json"`, but no other format is implemented. Without a TOON encoder
the field is essentially a placeholder, and Phase 3's MCP server
(`FOLIO-H-017`) cannot expose `format="toon"` to agents that need
the token reduction.

## Decision

- Use a header-then-rows layout (`[N]{cols}:` followed by one
  comma-delimited body line per record). This is more compact than
  JSON for arrays of records that share a common shape (the typical
  Folio case) without committing to a niche binary format.
- Header field order is the union of keys across all records, sorted
  by first-appearance to match the records.jsonl insertion order
  the rest of the SDK preserves.
- A cell whose JSON form is identical to the value's string form
  (after stripping trailing zeroes for floats) is emitted unquoted.
  Anything else is JSON-encoded so the consumer can recover the
  exact value if it parses cell-wise.
- Skip a TOON decoder for Phase 3; tests pin output strings to
  catch regressions without growing the encoder surface.

## Permanent Fix

- `scripts/harness_check.py` requires `src/folio/_toon.py` and
  `tests/test_toon.py`.
- The `format == "toon"` integration test in `test_sheet.py` /
  `test_toon.py` pins the envelope shape so a future change to the
  `format` field is visible.

## Next Check

`FOLIO-H-017` (MCP server) will accept `format="toon"` on its
`list_records` tool and forward to the SDK call. Make sure the MCP
tool's docstring teaches agents when to prefer TOON over JSON.
