# Design Docs

This directory is the canonical home for Folio design intent and design
decision history. Keep root `AGENTS.md` as the short routing layer and update
these docs when architecture or product direction changes.

## Current Documents

- [Overview](overview.md): complete product and technical design, including
  the current implementation checkpoint.
- [Architecture Decision Records](adrs/README.md): accepted, proposed,
  rejected, deprecated, or superseded decisions with rationale and
  confirmation checks.

## Update Rules

- Update [overview.md](overview.md) when the target architecture, current
  implementation checkpoint, roadmap, terminology, or open risks change.
- Add or update an ADR when a decision would otherwise be rediscovered or
  re-debated by future agents.
- Keep ADRs short and single-decision. Put broad system narrative in the
  overview or a focused design doc.
- Every accepted ADR must include a `## Confirmation` section that names the
  command, test, smoke, structural check, or review path that keeps the
  decision enforceable.
- Run `make validate-docs` for docs-only changes and `make verify` before
  declaring mixed code/docs work complete.

## Harness Contract

The docs harness validates that:

- this index exists and links the canonical design overview and ADR index;
- root `design-doc.md` stays a compatibility pointer instead of a stale copy;
- every ADR filename follows `NNNN-kebab-title.md`;
- every ADR is indexed from [adrs/README.md](adrs/README.md);
- required ADR sections are present;
- accepted ADRs include mechanical confirmation guidance.
