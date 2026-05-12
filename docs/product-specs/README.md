# Product Specs

Product specs describe the next executable slice of Folio. Each spec is
self-contained enough that an agent can land it in one bounded loop without
reading the entire design overview.

| Spec | Phase | Status |
|---|---|---|
| [Phase 0 — minimum sheet](phase-0-minimum-sheet.md) | 0 | implemented (`FOLIO-H-002` … `FOLIO-H-005`) |
| [Phase 1 — derivations and provenance](phase-1-derivations-and-provenance.md) | 1 | implemented (`FOLIO-H-009` … `FOLIO-H-012`) |
| [Phase 2 — scripts and README frontmatter](phase-2-scripts-and-readme-frontmatter.md) | 2 | spec only; broken into `FOLIO-H-014` … `FOLIO-H-015` |
| [Phase 3 — TOON output](phase-3-mcp-server-and-toon-output.md) | 3 | implemented (`FOLIO-H-018`); MCP server removed by `FOLIO-H-031` |
| [Phase 4 — extension kinds and datapackage.json](phase-4-extension-kinds-and-datapackage.md) | 4 | spec only; broken into `FOLIO-H-020` … `FOLIO-H-022` |
| [Phase 5 — Viewer](phase-5-viewer.md) | 5 | spec only; broken into `FOLIO-H-024` … `FOLIO-H-025` |

Specs reference the canonical design at
[`docs/design-docs/overview.md`](../design-docs/overview.md) for vocabulary
and constraints. Decisions that bind future agents move into ADRs under
[`docs/design-docs/adrs/`](../design-docs/adrs/).
