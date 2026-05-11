<p align="center">
  <img src="https://raw.githubusercontent.com/nyuta01/folio/main/apps/desktop/build/icon-128.png" alt="Folio" width="96" height="96" />
</p>

# Folio Agent Skills

A distributable pack of `SKILL.md` files that teach AI coding agents
how to use Folio. Compatible with the **`skills.sh`** ecosystem
(Claude Code, Cursor, Cline, GitHub Copilot, Codex, Windsurf, Gemini,
and 12+ others) and with the **TanStack Intent registry** (npm-based
discovery).

**This is not** the per-sheet skills design at
[`docs/methodology/sheet-skills-design.md`](../docs/methodology/sheet-skills-design.md),
which describes domain procedures that ship inside a sheet's tarball.
*This* directory ships product knowledge: how to author a Folio
sheet, configure derivations, debug a materialize, etc. — knowledge
about Folio itself, not about a specific dataset.

## Installing

### Via skills.sh (recommended)

```bash
# Project-scoped install (recommended for Folio work)
npx skills add nyuta01/folio

# Global install
npx skills add -g nyuta01/folio

# Install just one skill
npx skills add nyuta01/folio --skill add-derivation-ai
```

The CLI symlinks the skill files into your agent's discovery path
(`.claude/skills/` for Claude Code, `.agents/skills/` for Cursor,
etc.). Works with 18+ agent runtimes.

### Via npm (TanStack Intent compatible)

```bash
npm install --save-dev folio-agent-skills
# or
pnpm add -D folio-agent-skills
```

The package ships the same `SKILL.md` files and is tagged with the
`tanstack-intent` keyword so the
[TanStack Intent registry](https://tanstack.com/intent/registry)
indexes it automatically.

### Manual

```bash
# Drop the directory into your project
git clone https://github.com/nyuta01/folio.git /tmp/folio
cp -r /tmp/folio/skills/*/ .claude/skills/
```

## What's included

| Skill | When to invoke |
|---|---|
| `folio-quickstart` | First-time setup of a Folio sheet from scratch. |
| `add-derivation-ai` | Wire up an LLM-powered derivation with prompts and structured output. |
| `add-derivation-cross-sheet` | Join two sheets 1:1 by primary key. |
| `debug-failed-materialize` | Diagnose per-cell failures from `Sheet.materialize`'s envelope. |

More are landing — see the [task list](https://github.com/nyuta01/folio/issues?q=label%3Askills)
for `add-derivation-{python,sql,http,import}`, `migrate-csv-to-folio`,
`set-up-mcp-server`, `audit-provenance`, `export-frictionless`, and
`upgrade-folio-version`.

## SKILL.md format

Every skill is a directory containing exactly one `SKILL.md`:

```
skills/
└── add-derivation-ai/
    └── SKILL.md
```

Frontmatter follows the universal format used by Claude Skills,
skills.sh, and TanStack Intent:

```yaml
---
name: add-derivation-ai            # required, lowercase, hyphenated
description: >-
  One-line summary used by agents to decide whether the skill applies.
  Should reference Folio explicitly so it doesn't fire for unrelated tasks.
---
```

The body is plain markdown. Folio skills follow these conventions:

1. **Lead with a one-line summary** — agents quote it.
2. **Use a "When this skill applies" section** so the model can
   self-check.
3. **Provide a checklist or numbered procedure**, not prose.
4. **Embed at least one minimal complete example** (a real `derivations/*.yaml`
   block, a real CLI invocation).
5. **End with a "Verify" section** the agent can run to confirm
   success.

## Authoring a new skill

1. Pick a directory name: `kebab-case`, scoped (e.g.
   `add-derivation-sql`, not `sql`).
2. Create `skills/<name>/SKILL.md` with the frontmatter above.
3. Test discovery locally:
   ```bash
   npx skills add . --skill <name>
   ls .claude/skills/   # verify the link
   ```
4. Validate against the conventions above.
5. Send a PR.

## License

MIT (same as Folio). See the repo root.
