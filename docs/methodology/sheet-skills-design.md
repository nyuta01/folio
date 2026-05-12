# Folio skills — design proposal

**Status:** proposal (2026-05-11). Research-driven, not yet implemented.

## Goal

Let a Folio sheet ship **packaged how-to knowledge** — short, named
procedures that an agent or human can pick up when they open the
sheet. Examples:

- "Fill missing customer industries"
- "Run weekly revenue refresh"
- "Review onboarding queue"

The point is that a CLI-driven agent can *discover the right
operating instructions for the domain* without relying on a system
prompt baked into the agent runtime — the sheet itself carries the
operating manual.

## Why not just lean on existing mechanisms?

We surveyed the current candidates:

| Mechanism | Ships with | Discoverability | Auto-invoke | Per-sheet portability |
|---|---|---|---|---|
| **Claude Skills** (`.claude/skills/<name>/SKILL.md`) | Claude Code / Desktop | by tool runtime | ✓ (model-detected) | ✗ (lives in repo / home, not in the sheet directory) |
| **Custom GPT instructions** | OpenAI | per-GPT only | ✗ | ✗ |
| **Cursor/Continue rules** | per-tool | per-tool | partial | ✗ |

None of them alone delivers all properties. **Claude Skills**
nail discoverability and auto-invoke but live outside the sheet — a
sheet that gets `tar`-ed loses them. We therefore propose a hybrid:
store skills inside the sheet (portability), surface them via the
CLI/SDK (discoverability), and optionally generate a Claude Skills
mirror as an export.

## Layout (inside a sheet)

```
my-sheet/
├── contract.yaml
├── records.jsonl
├── derivations/
├── scripts/
├── skills/                       ← NEW
│   ├── refresh-revenue.md
│   ├── audit-provenance.md
│   └── fill-missing-industries.md
└── README.md
```

One markdown file per skill, basename used as the skill's id.

## Skill file format

```markdown
---
name: refresh-revenue
description: Re-run cross-sheet revenue lookup for stale records and
             report what changed since the last full run.
audience: agent                # agent | human | both (default: agent)
arguments:                     # optional — filled into the body via {arg}
  - name: only_country
    description: ISO-3166 alpha-2 code to scope the refresh to one country.
    required: false
tools:                         # optional allow-list of Folio surfaces
  - materialize
  - list_records
  - provenance
allowed_actors:                # optional, same fnmatch syntax as x-editable-by
  - agent:ops:*
  - agent:human
---

# Refresh revenue

Refresh the `current_revenue_usd` field for every record where the
upstream `customer-revenue` sheet has changed since the last
materialize, and surface a per-row diff.

## Steps

1. Call `materialize(targets=["current_revenue_usd"])` — Folio's cache
   ensures only stale rows recompute.
2. Read the result envelope — non-zero `materialized` means real
   updates landed.
3. For each updated `record_id`, fetch the latest `provenance` entry
   to capture the new `input_hash` and the `cross_sheet` source row.
4. Summarize: `<n> rows updated, <n> rows still stale, <n> failures`.

## Notes

- Don't materialize unless the upstream sheet's `provenance.jsonl`
  has changed. Cheap check: read the last line and compare timestamps.
- If `only_country` is supplied, prefilter via
  `list_records(filter="country = '{only_country}'")`.
```

Body is plain markdown — no executable code paths. Anything that
needs side effects goes through Folio's existing CLI or SDK methods.

## Validation

`folio validate` (and `Sheet(...)`) check, per skill file:

1. YAML frontmatter parses; `name` and `description` present.
2. `name` matches `^[a-z][a-z0-9-]*$` (URL-safe).
3. `name` matches the file basename.
4. `audience` ∈ `{agent, human, both}` if present.
5. `tools` only references real SDK method names (cross-checked
   against the list in §7.2 of the spec).
6. `allowed_actors` patterns are well-formed `fnmatch`.
7. `arguments[].name` matches `^[a-z][a-z0-9_]*$`; `{name}`
   placeholders in the body are all declared.

`README.md` frontmatter's existing `agent_skills: list[str]` becomes
a *manifest* — every name in it must resolve to a `skills/<name>.md`,
and vice versa (every `skills/*.md` should be listed). Violation is a
warning, not an error, so external consumers can ship a subset.

## SDK surface

```python
sheet.list_skills() -> list[Skill]
sheet.get_skill(name) -> Skill | None
sheet.render_skill(name, args: dict[str, Any]) -> str  # frontmatter-stripped, args-filled
```

## CLI surface

```
folio skill list <sheet>
folio skill show <sheet> <skill-name> [--arg name=value]
folio skill validate <sheet>
```

## Optional: Claude Skills bridge

`folio export claude-skills <sheet> [--out .claude/skills/]` emits
one directory per skill in the layout Claude Code expects:

```
.claude/skills/
└── example-customers__refresh-revenue/
    └── SKILL.md         # frontmatter + body
```

Frontmatter is mapped 1:1 where keys exist in both formats (`name`,
`description`); Folio-specific keys (`tools`, `allowed_actors`) drop
to the body as a "Constraints" section. The bridge is **derived,
read-only output** — the sheet's `skills/` is always the source of
truth.

## Why this shape

| Property | Mechanism |
|---|---|
| Portability — sheet is a self-contained tarball | skills live inside the sheet |
| Discoverability for agents | `folio skill list/show` and `Sheet.list_skills` |
| Auto-invoke for Claude users | optional `claude-skills` export |
| Versioning | the sheet's own `version` covers it; skills are part of the sheet |
| Naming collisions | one skill id namespace per sheet |
| Security | prose-only; tools listed are advisory; real authorization stays in SDK write paths |
| Multilingual | the skill body can be authored in any language; `audience` lets sheets ship per-audience copies |

## Out of scope (explicit non-goals)

- **Executable skills.** Skills do not embed shell or Python. If a
  user needs side-effects, that's a `derivations/` entry plus a skill
  that *describes when to materialize it*. Keeps the security
  posture simple.
- **Cross-sheet skills.** A skill belongs to exactly one sheet today.
  A future "skill collection" object can compose them; we are not
  designing for that now.
- **Skill chaining / agent loops.** Skills describe procedures; the
  agent runtime decides how to execute them. Folio does not run an
  agent.

## References

- Claude Skills (official): <https://code.claude.com/docs/en/skills>
- Agent Skills open standard: <https://agentskills.io>
## Implementation rollout

Tracked as separate tasks. See the project task list for `Folio Skills:` items.
