# FOLIO-H-020 Plan: sql and http Extension Kinds

## Goal

Promote `kind` from a closed Phase 1 set (`ai`, `import`) into a real
extension point by shipping the first two extension kinds named in
§8.5: `sql` and `http`. Both flow through the existing
`Sheet.materialize` loop so they inherit the cache, provenance, and
human-override semantics from Phase 1.

## Scope

- New package `src/folio/kinds/`:
  - `__init__.py` re-exports `SQLDerivation`, `HTTPDerivation`,
    `execute_sql`, `execute_http`, and the `HTTPTransport` Protocol.
  - `_sql.py` with `SQLDerivation` (Pydantic v2 model with required
    `expression`, optional `output_schema` for multi-target,
    SELECT-only enforcement re-using
    `folio._query.ensure_select_only`) and `execute_sql(derivation,
    inputs, *, contract, records_path)` returning
    `{target: value, ...}`.
  - `_http.py` with `HTTPDerivation` (Pydantic v2 model: `url`,
    `method`, `headers`, optional `body_template`,
    `response_path` for single-target / `response_schema` for
    multi-target), an `HTTPTransport` Protocol with one
    `request(method, url, headers, content) -> HTTPResponse`
    method, an `HTTPXTransport` adapter, and a
    `StubHTTPTransport` for tests / smoke. `execute_http` expands
    `{{ field }}` templates in `url` and `body_template`, walks
    a dot-separated `response_path`, and returns the value map.
- `src/folio/derivation.py` extends the discriminated union to
  include the two new kinds.
- `src/folio/_cache.py`: `compute_input_hash` accepts an
  `extra_components: dict[str, Any] | None = None` so extension
  kinds can fold their unique payload keys into the canonical hash
  without growing the helper's positional surface.
- `src/folio/sheet.py`: `Sheet.materialize` adds branches that
  invoke `execute_sql` / `execute_http`. The cache is bypassed for
  `sql` because its result depends on the entire `records.jsonl`
  (folded into the hash via `records_file_hash`); the cache is
  honored for `http` (URL + body + headers determine the response).
- `pyproject.toml` adds `httpx>=0.27` to runtime dependencies.
- `tests/test_kind_sql.py` covers: single-target value extraction,
  multi-target column projection, parameter passthrough from
  inputs, SELECT-only rejection of write keywords, multi-target
  schema mismatch rejection.
- `tests/test_kind_http.py` covers: GET with template URL,
  POST with body template, header forwarding, dot-path response
  resolution, multi-target via response_schema, HTTP error
  surfacing, `StubHTTPTransport` canned response by URL +
  request-recording.
- Integration tests under `tests/test_materialize.py` extension:
  one ai + one sql derivation in dependency order, materialize
  populates both correctly; one http derivation populates a value
  using `StubHTTPTransport`.
- `scripts/_extension_kinds_smoke.py` materializes one sql and one
  http derivation against a temp sheet using stubs.
  `scripts/smoke-extension-kinds.sh` invokes it.
- `Makefile` adds `extension-kinds-smoke` and includes it in
  `verify`.
- `scripts/harness_check.py` requires the new package, tests,
  smoke files, and the new verify-target line.

## Out of scope

- `python` and `cross_sheet` extension kinds. `FOLIO-H-021`.
- A formal third-party plug-in registry. The current "registry" is
  the discriminated union; promotion to a real plug-in surface is
  reopened only when a real consumer appears.
- `datapackage.json` generation. `FOLIO-H-022`.

## Evidence

- `make verify` passes locally with the expanded `python-test` and
  the new `extension-kinds-smoke`.
- A sql derivation that aggregates over `records` materializes
  the expected value for each record.
- An http derivation against `StubHTTPTransport` returns the canned
  response body.

## Observation

Phase 1 ships standard `ai` and `import` kinds, but the design
overview §8.5 names four extension kinds and the ecosystem cannot
practically wait for all four to land at once. Sql and http are the
"thin" ones that do not depend on other extension surfaces and can
land first.

## Decision

- Extend the discriminated union rather than introduce a runtime
  plug-in registry. The union is statically inspectable, plays
  well with Pydantic v2, and avoids the ordering problems a runtime
  registry introduces.
- Inject the HTTP transport through the existing `Sheet.materialize`
  signature (mirrors ADR-0009's AIClient pattern) so tests can
  swap a `StubHTTPTransport` without monkeypatches.
- Skip the cache for `sql` because its result depends on the entire
  `records.jsonl` snapshot. The records-file hash still feeds
  `input_hash` so provenance and stale detection stay correct.
- Use a tiny dot-path resolver for `response_path` /
  `response_schema` in `http` rather than pulling in a JSONPath
  library; the spec example uses simple dotted paths.

## Permanent Fix

- `make verify` runs the new smoke. Removing a kind, the smoke,
  or the extension-kinds-smoke verify line fails the gate.
- The discriminated union plus `extra="forbid"` rejects malformed
  bodies (e.g., `kind: sql` with stray fields) at parse time.
- The integration tests in `test_materialize.py` pin the
  end-to-end behavior so a refactor cannot quietly break the
  multi-kind composition.

## Next Check

`FOLIO-H-021` adds `python` (depends on Phase 2 `FOLIO-H-014`) and
`cross_sheet` (introduces foreign-sheet stale detection). It will
follow the same dispatch pattern: extend the discriminated union,
add an executor, branch in `Sheet.materialize`.
