# FOLIO-H-011 Plan: ai Kind Driver

## Goal

Land the `ai`-kind execution driver so `FOLIO-H-012` can wire a
materialize loop on `Sheet` that calls the Anthropic SDK in production
and a deterministic stub in tests, without forcing every contributor to
hold a live API key for `make verify`.

## Scope

- `src/folio/_ai_kind.py`:
  - `AIResponse` dataclass (text, input_tokens, output_tokens).
  - `AIClient` Protocol with one method (`messages_create`) so both
    the real Anthropic SDK and the test stub satisfy it.
  - `expand_template(template, inputs)` for the spec's
    `{{ field_name }}` subset (the only template form allowed by §8.2
    of the design overview).
  - `materialize_ai(derivation, inputs, *, client,
    prompt_body=None, max_tokens=1024) -> AIResult` that renders the
    prompt, calls the client, parses text or JSON output, validates
    multi-target `output_schema` keys, and computes `cost_usd` from a
    small per-model price table.
  - `AnthropicClientAdapter` wrapping the real Anthropic SDK so the
    rest of the codebase only depends on the `AIClient` Protocol.
  - `StubAIClient` for tests and offline materialize. Supports
    canned responses keyed by prompt substring and a fallback
    callable.
  - `AIKindError` for invalid JSON, missing targets, missing template
    fields, and unsupported configurations.
- `pyproject.toml` adds `anthropic` to runtime dependencies.
- `tests/test_ai_kind.py` covers: template expansion (single field,
  multiple fields, missing field rejection), text-output single-
  target, JSON-output single-target, JSON-output multi-target with
  schema, JSON-output missing target rejection, JSON-output not an
  object rejection, invalid JSON rejection, cost calculation for a
  known model, and `cost_usd is None` for an unknown model.
- New ADR `0009-ai-client-protocol-and-deterministic-stub.md`
  recording the dependency-injection design (Protocol + Adapter +
  Stub) so future agents do not re-introduce direct Anthropic SDK
  calls inside the driver.
- `scripts/harness_check.py` requires the new module, the test, and
  the new ADR.

## Out of scope

- Wiring `materialize_ai` into a `Sheet.materialize()` loop. That is
  the job of `FOLIO-H-012` together with the CLI verbs and the
  materialize smoke.
- Retry policy beyond what the Anthropic SDK already provides.
  Tracked under design overview Appendix B.
- Live network smoke. The harness must remain runnable offline; the
  Anthropic SDK is exercised only via the adapter signature.

## Evidence

- `make verify` passes locally with the expanded `python-test`.
- The stub-driven tests cover every branch of `_parse_response_to_values`
  without invoking the real SDK.

## Observation

`FOLIO-H-009` and `FOLIO-H-010` give us derivations, the cache, and
the provenance log, but no actual computation surface for the `ai`
kind. The materialize loop in `FOLIO-H-012` can only start once a
deterministic, mockable driver exists.

## Decision

- Hide the Anthropic SDK behind a single-method Protocol so the
  driver, the CLI, and the test layer all consume the same shape.
  `AnthropicClientAdapter` is the only place that imports
  `anthropic`.
- Use a tiny per-model `PRICE_TABLE_USD` for cost calculation.
  Unknown models yield `cost_usd=None`; provenance entries surface
  whatever the table reports without inventing numbers.
- `StubAIClient` accepts canned responses keyed by prompt substring
  plus an optional fallback callable. That covers both fixed-response
  smokes (CLI tests) and table-driven scenarios (multi-record
  materialize).
- `materialize_ai` is a pure function that takes the rendered prompt
  body alongside the derivation. The caller (the materialize loop in
  `H-012`) is responsible for resolving `prompt_ref` to a string and
  passing it in. That keeps the driver agnostic to filesystem layout
  while still letting the loop pass the right body for `input_hash`.

## Permanent Fix

- ADR-0009 pins the Protocol + Adapter + Stub design so a future
  agent cannot quietly couple `_ai_kind.py` directly to the
  Anthropic SDK. `make validate-docs` enforces the ADR's structure.
- `scripts/harness_check.py` requires `src/folio/_ai_kind.py`,
  `tests/test_ai_kind.py`, and the new ADR file.
- `make verify` runs the stub-driven tests offline, so the gate stays
  reproducible without a live API key.

## Next Check

`FOLIO-H-012` adds `Sheet.materialize`, `Sheet.materialization_status`,
`Sheet.provenance`, the matching CLI verbs, and a deterministic
`scripts/smoke-materialize.sh` that walks the §23.3 scenario through
`StubAIClient` so the smoke can run without network access.
