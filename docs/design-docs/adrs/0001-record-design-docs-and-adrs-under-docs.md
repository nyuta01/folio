# ADR-0001 Record Design Docs and ADRs Under Docs

- **Status**: `accepted`
- **Date**: `2026-05-10`
- **Decision makers**: `agent`
- **Related**: `docs/design-docs/README.md`, `docs/design-docs/overview.md`

## Context

The initial Folio product design lived at repository root as `design-doc.md`.
That worked for bootstrapping, but it made the root file both a large design
document and a harness entry point. As the project grows, agents need a
structured docs hierarchy that separates durable design intent, decision
history, product specs, and execution plans.

Harness Engineering guidance also favors a short `AGENTS.md` routing layer
and a structured repository-local knowledge base that can be linted for
reachability and drift.

## Decision

Design documents and Architecture Decision Records live under
`docs/design-docs/`.

- `docs/design-docs/overview.md` is the canonical product and technical
  design, including the current implementation checkpoint.
- `docs/design-docs/adrs/` is the decision log.
- Root `design-doc.md` remains only as a compatibility pointer.
- `make validate-docs` enforces the design-doc and ADR structure.

## Consequences

- Future agents have a single discoverable home for design rationale.
- Root `AGENTS.md` can stay compact and point to the design index.
- ADRs can be mechanically checked for required structure and confirmation
  guidance.
- Existing references to root `design-doc.md` need to be updated or treated
  as compatibility references.

## Confirmation

Run:

```bash
make validate-docs
make verify
```

The docs validation gate checks that design docs are indexed, root
`design-doc.md` is only a pointer, and ADR files follow the required
structure including a confirmation path for accepted decisions.

## Alternatives Considered

- Keep the canonical design document at repository root. This preserves the
  original path but does not scale to multiple design docs or ADRs.
- Put ADRs under `docs/adr/`. This follows some ADR tools, but
  `docs/design-docs/adrs/` keeps rationale next to the canonical design docs.
