# ADR-0007 Match x-editable-by with fnmatch Patterns

- **Status**: `accepted`
- **Date**: `2026-05-10`
- **Decision makers**: `agent`
- **Related**: `docs/design-docs/overview.md` §6.4, §9.3

## Context

The Folio specification keeps the permission model deliberately small.
`x-editable-by` is **optional**: without it, anyone can edit; with it,
"interpretation is up to the implementation (pattern-match against actor
strings)" (§9.3). The design overview shows `agent:*` and `human:alice`
as illustrative patterns. Actor strings themselves are free-form (§9.2).

The reference implementation must commit to a concrete pattern dialect
or every CLI/SDK consumer ends up unsure what `agent:*` actually means.

## Decision

The reference implementation matches `x-editable-by` patterns against
the operation's `actor` string using Python's `fnmatch.fnmatchcase`,
with two trivial fast paths:

- An exact string equality (`pattern == actor`) matches.
- The single-character wildcard `*` matches any actor.
- All other patterns flow through `fnmatchcase`, which supports `*`,
  `?`, and `[seq]` glob metacharacters.

`x-editable-by` is enforced only on fields that appear in the upserted
record. Untouched fields are not rechecked. Fields without
`x-editable-by` allow any actor.

Real authentication and authorization (JWT, OAuth, RBAC) remain the
caller's responsibility. The reference implementation only enforces the
pattern check; it does not validate the identity behind the actor
string.

## Consequences

- A schema that declares `x-editable-by: ["agent:*", "human:*"]` does
  what users already expect from glob-style permission lists.
- Implementations in other languages that pick a different pattern
  dialect (PCRE, regex, RBAC roles) are still spec-conformant but
  produce different decisions on the same `x-editable-by` value. That
  is the cost of the spec leaving the dialect unspecified.
- A future need for richer rules (deny-by-default, role hierarchies,
  signed actors) replaces or augments this matcher rather than
  overloads it.

## Confirmation

`tests/test_sheet.py` covers `editable_by` allow / deny / no-restriction
under `make verify`. `tests/test_cli.py` exercises the matching error
path through the CLI. The decoupling between authentication and
authorization is enforced by leaving `actor` as a free-form string
across the SDK and CLI.

## Alternatives Considered

- Regex (`re.fullmatch`) patterns. More expressive, but requires users
  to escape literal `:` and to learn Python regex. Glob patterns
  carry less surprise for `agent:*`-style values. Rejected.
- A pluggable matcher with a registry of strategies. Premature
  abstraction. Reopen if a real second strategy appears.
- Treat `x-editable-by` as an exact-match list (no wildcards). Forces
  users to enumerate every agent/human, which loses the obvious
  ergonomic shape from the design overview. Rejected.
