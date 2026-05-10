# ADR-0002 Use Python as the Reference Implementation

- **Status**: `accepted`
- **Date**: `2026-05-10`
- **Decision makers**: `agent`
- **Related**: `docs/design-docs/overview.md` §20.1

## Context

The Folio specification in `docs/design-docs/overview.md` is deliberately
language-independent: any implementation that honors the file layout,
operations, and invariants in Part 1 is conformant. This project still
needs to ship a single first-party reference implementation so the design
remains executable, the harness has something concrete to verify, and the
agent ecosystem (Anthropic's docx/xlsx/pdf skills, the official
code execution tool) gets a shape it already runs.

§20.1 of the design overview already argues for Python on those grounds.
Without an ADR, that justification lives only in the long-form design doc
and a future agent could legitimately reopen the question.

## Decision

The reference implementation provided by this repository is written in
Python, packaged under `src/folio/` with a hatchling build backend, and
managed through `uv`. Dependencies are pinned in `uv.lock` and the project
script `folio = "folio.cli:main"` is the canonical CLI entry point.

Other-language implementations remain welcome and are expected: this ADR
binds the **reference** implementation only, not the spec.

## Consequences

- The harness can require concrete deterministic checks (`python-test`,
  `cli-smoke`) without abstracting over a language plug point.
- New contributors install one toolchain (`uv`) and run one command
  (`make verify`) to reproduce CI.
- Phase 0 dependencies (`pydantic`, `pyyaml`, `duckdb`, `filelock`,
  `typer`) constrain the runtime to Python 3.13+.
- A second-language implementation (Go, Rust, TypeScript) must re-derive
  conformance against the spec rather than against the Python codebase.

## Confirmation

`make verify` runs `python-test` (62 pytest cases) and `cli-smoke`
through `uv run --frozen folio …`. `scripts/harness_check.py` requires
`pyproject.toml`, `src/folio/__init__.py`, `src/folio/cli.py`,
`src/folio/sheet.py`, and the contract / sheet / CLI test files; removing
any of them fails the gate.

## Alternatives Considered

- TypeScript reference implementation. Aligns with coding-agent runtimes
  (Claude Code, Cursor) but mismatches the official Anthropic skills
  ecosystem (Python). Rejected for Phase 0; revisitable if the Viewer or
  MCP layer grows materially.
- Go reference implementation. Strong static typing and single-binary
  distribution, but yet-to-mature ecosystem for ODCS / Frictionless /
  RFC 8785. Rejected for Phase 0.
