# Architecture Decision Records

ADR files capture one architecturally meaningful decision each. Use them when
a choice changes system boundaries, persistence, protocol behavior,
specification surface, security, operability, or the agent harness itself.

## Records

| ADR | Status | Decision |
|---|---|---|
| [0001](0001-record-design-docs-and-adrs-under-docs.md) | accepted | Record design docs and ADRs under `docs/design-docs/` |

## Status Values

- `proposed`: under discussion and not yet binding.
- `accepted`: binding for new work until superseded.
- `rejected`: considered and intentionally not chosen.
- `deprecated`: no longer recommended, but no single replacement ADR exists.
- `superseded`: replaced by a later ADR that must be linked.

## New ADR Checklist

1. Copy [template.md](template.md).
2. Name the file `NNNN-kebab-title.md` with the next sequence number.
3. Add it to the Records table.
4. Fill every required section.
5. Include a confirmation path for accepted decisions.
6. Run `make validate-docs`.
