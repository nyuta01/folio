# FOLIO-H-015 Plan: README YAML Frontmatter

## Goal

Land the AI-oriented metadata layer for a sheet so agents that read
`README.md` directly (without going through the SDK) can discover the
sheet's purpose and default actor in a typed, validated form.

## Scope

- `src/folio/readme.py`:
  - `Frontmatter` Pydantic v2 model with required `purpose` and
    `default_actor`, optional `tags: list[str]`,
    `links: dict[str, str]`, and `agent_skills: list[str]`.
  - `parse_frontmatter(text)` extracting the leading
    `---\n…\n---\n` block, parsing it as YAML, and returning the
    validated model. Returns `None` when no frontmatter is present;
    raises `ReadmeError` on malformed delimiters / YAML / model
    validation.
  - `load_readme_metadata(sheet_path)` reading
    `<sheet>/README.md` and returning the parsed model or `None`.
- `Sheet.metadata` property exposing the parsed frontmatter (lazy
  re-read; the cost is cheap and matches `Sheet.contract`'s eager
  posture).
- `folio validate` enhancement:
  - Always reports the contract + records lines (existing behavior).
  - When `README.md` is present, attempts to parse the frontmatter.
  - Without `--strict`, malformed frontmatter prints a `warning:`
    line on stderr but exits zero. With `--strict`, malformed
    frontmatter exits non-zero.
  - When the frontmatter is valid, prints
    `README.md frontmatter is valid (purpose: …, default_actor: …)`.
- `tests/test_readme.py` covering: no README, README without
  frontmatter, valid minimal frontmatter, frontmatter with all
  optional fields, missing required fields, malformed delimiters
  (no closing `---`), invalid YAML, unknown attribute rejection,
  and `Sheet.metadata` integration.
- `tests/test_cli.py` extension: validate command in default mode
  (warning), `--strict` mode (error), and the success-path message
  for a sheet with valid frontmatter.
- `scripts/harness_check.py` requires the new module and the new
  test file.

## Out of scope

- Aligning `agent_skills` with the upstream Anthropic Agent Skills
  schema. Tracked as an open issue in the design overview Appendix B.
- Surfacing frontmatter through MCP tool docstrings. `FOLIO-H-017`
  picks that up when the MCP server exists.
- Auto-resolving the `default_actor` field at write-time. The CLI
  still requires `--actor`; `default_actor` is informational for
  Phase 2.

## Evidence

- `make verify` passes locally with the new pytest cases.
- `folio validate` against a sheet with valid frontmatter prints
  the expected line.

## Observation

The Phase 2 spec commits to a YAML frontmatter convention but no
parser exists. Without a typed model, `agent_skills` integration in
later phases would have to rediscover the shape from
`docs/product-specs/phase-2-scripts-and-readme-frontmatter.md`.

## Decision

- Use Pydantic v2 + `extra="forbid"` so unknown frontmatter
  attributes fail fast (matching the contract.yaml convention).
- Treat the frontmatter delimiter strictly (`^---\\s*\\n` then a
  matching closing `---\\s*\\n`). Anything else raises so a
  half-typed delimiter cannot pass silently.
- Treat metadata as a lazy property on `Sheet` rather than loading
  eagerly in `__post_init__`. README.md is optional; pulling it
  into the constructor would make every read pay for the parse.
- Default `folio validate` is non-strict because frontmatter is an
  affordance, not a hard contract. `--strict` exists for CI
  pipelines that want to block on it.

## Permanent Fix

- `scripts/harness_check.py` requires `src/folio/readme.py` and
  `tests/test_readme.py`.
- The validate-command tests pin the warning vs error semantics
  for `--strict` so future agents do not silently make malformed
  frontmatter fatal by default.

## Next Check

`FOLIO-H-017` (Phase 3 MCP server) will surface
`Sheet.metadata.purpose` in the tool's `get_contract` response so
agents can read the sheet's intent without an extra round trip.
