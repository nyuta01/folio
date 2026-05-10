# ADR-0009 AI Client Protocol and Deterministic Stub

- **Status**: `accepted`
- **Date**: `2026-05-10`
- **Decision makers**: `agent`
- **Related**: `docs/design-docs/overview.md` §8.2, §15-§17;
  `docs/product-specs/phase-1-derivations-and-provenance.md`

## Context

Phase 1 introduces the `ai` derivation kind, which calls the Anthropic
SDK to fill derived fields. Two hard constraints follow from earlier
choices:

1. **`make verify` must run offline.** Tests, smokes, and CI cannot
   require a live API key (ADR-0008 makes the cache rebuildable; the
   harness must stay reproducible too).
2. **The driver must stay swappable.** A second-language reference or
   a future provider should be able to replace the SDK without
   rewriting the materialize loop.

A naive implementation that imports `anthropic` directly inside the
driver violates both constraints: tests would either need network
access or monkey-patch a private import path, and replacing the
provider would require touching every call site.

## Decision

The `ai`-kind driver is built around a single-method `AIClient`
Protocol:

```python
class AIClient(Protocol):
    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, Any]],
    ) -> AIResponse: ...
```

Two implementations satisfy it:

- `AnthropicClientAdapter` is the only place in the codebase that
  imports `anthropic`. It wraps `anthropic.Anthropic` and converts the
  SDK's response shape into the local `AIResponse` dataclass.
- `StubAIClient` is a deterministic in-process implementation used by
  tests and the future offline materialize smoke. It accepts canned
  responses keyed by a substring of the rendered prompt and an
  optional `responder` callable for table-driven scenarios.

`materialize_ai(derivation, inputs, *, client, prompt_body=None,
max_tokens=1024)` is a pure function that takes the rendered prompt
body (the caller resolves `prompt_ref` to a string), expands the
`{{ field }}` template, calls the client, parses the response into
`{target: value}`, and returns `AIResult` (values, token counts,
`cost_usd`, raw text).

Production callers pass `AnthropicClientAdapter()`; tests pass
`StubAIClient()`. No conditional code in the driver branches on
"production vs test" mode.

## Consequences

- The Anthropic SDK is required at runtime (`anthropic` is a runtime
  dependency in `pyproject.toml`) but never imported on the test
  fast path.
- A future second provider becomes a sibling adapter that satisfies
  the same Protocol. The driver is unchanged.
- Cost calculation lives in a small per-model `PRICE_TABLE_USD`. New
  models fall through to `cost_usd=None` until the table is updated;
  provenance entries surface what is known instead of inventing
  numbers.
- The Protocol method is intentionally narrow (`messages_create` with
  positional-or-keyword arguments). Higher-level Anthropic features
  (tools, system prompts, streaming) are not exposed; they would be
  added as separate methods on the Protocol if Phase 1 needs them.

## Confirmation

`tests/test_ai_kind.py` exercises every branch of the driver via
`StubAIClient` without importing `anthropic`. Future drift would
either fail those tests (if the driver acquires conditional
production paths) or require a new ADR (if the Protocol surface
grows). `make verify` runs the suite under `python-test`. Reviewers
should reject any new direct `import anthropic` outside
`AnthropicClientAdapter`.

## Alternatives Considered

- **Direct `anthropic.Anthropic` calls inside `materialize_ai`**.
  Forces tests to monkey-patch the SDK, breaks offline `make verify`,
  and couples the driver to one provider. Rejected.
- **Environment-variable-based stub mode** (`FOLIO_AI_STUB=1`).
  Implicit, hard to compose with multiple stubs in one process, and
  surprises agents who debug behavior without reading env state.
  Rejected.
- **Pluggable provider registry**. Premature abstraction for a single
  provider in Phase 1; reopen if a second provider arrives.
