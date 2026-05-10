# FOLIO-H-027 Plan: Redesign Viewer per Claude Design handoff

## Goal

Re-implement the Folio Viewer frontend against the design handoff
bundle exported from claude.ai/design. The user iterated through ~10
design rounds (records grid → segmented tabs → integrated right panel
with rail → unified query bar → drawer with Result/History/Schema
tabs). The final state has zero top header, a single integrated
layout, and a Sheets-flavored grid with inline editing.

## Scope

- `viewer/src/App.tsx` — single composition: QueryBar at top, body
  with grid pane (selection bar + records grid + statusbar) and the
  right panel.
- `viewer/src/QueryBar.tsx` — unified query input that auto-detects
  WHERE vs full SELECT (via `isWhereOnly`), Run + Materialize
  buttons, and a resizable drawer (Result · History · Schema)
  reachable via `⌘K` or by running a query.
- `viewer/src/RecordsGrid.tsx` — plain HTML table (no TanStack);
  sticky header, per-cell hover provenance, derived/overridden/stale
  tints, pulse animation on freshly materialized cells, checkbox
  column with header-level select-all + bulk delete.
- `viewer/src/RightPanel.tsx` — three tabs (Schema · Activity ·
  Inspector). Persistent 44 px rail on the right edge; clicking the
  active rail icon collapses, clicking another tab switches and
  expands.
- `viewer/src/Icons.tsx` — 14 px stroke icons ported from the
  prototype.
- `viewer/src/types.ts` — shared types; aligned with the production
  source string `human_override` (not `human`).
- `viewer/src/api.ts` — extended with `runQuery`, `deleteRecords`,
  `getProvenanceHistory`.
- `viewer/src/useEventStream.ts` — returns the latest event plus a
  running log (capped at 500) so the activity tab can re-render on
  each frame.
- `viewer/src/index.css` — full rewrite from the prototype's design
  tokens. Drops the old "Modern Ledger" docs CSS in favor of the
  prototype's exact identity (warm cream `#fafaf7`, terra clay
  accent, slate-blue human, JetBrains Mono everywhere identifiers
  appear).
- `src/folio/sheet.py::materialization_status` — adds
  `derivation_kind` + per-kind counts (`python_count`, `sql_count`,
  `http_count`, `cross_sheet_count`) to the response so the right
  panel can color the per-target dot correctly.
- `scripts/harness_check.py` — required-files list updated for the
  new viewer file layout.

## Out of scope (per spec)

- **Editing the contract from the UI.** The prototype mocked
  `+ Add field`, type/required edits, and field deletion
  client-side. Production keeps §19.2's invariant — *contract
  changes go through file edits* — so the Inspector tab is
  read-only.
- **Per-cell-fill SSE frames.** The prototype simulated per-record
  cell_fill events. The production EventBus emits only
  `materialize.start` / `materialize.end` / `materialize.error`;
  the viewer reloads records + status on `materialize.end` and
  pulses cells whose value flipped from null.
- **Adding rows from the UI.** The prototype's `+ Add row` is
  removed in this pass. (Use `folio upsert` from the CLI; row
  creation through the viewer is a follow-up.)

## Out of scope (deferred)

- **Provenance on direct writes.** `Sheet.upsert_records` / 
  `delete_records` do not currently append `provenance.jsonl`
  lines. The viewer infers provenance lazily through
  `getProvenance`, so the layout is correct, but human edits don't
  yet leave a `human_override` trail. Tracked as a follow-up.

## Evidence

- `make verify` passes locally and in CI.
- The build product is **180 KB / 56 KB gzip** (down from 204 KB
  with TanStack Table removed).
- Hand-tested flow against `examples/customers/`:
  WHERE filter → derived rows highlight → click cell → editor →
  Enter → records re-fetched → click `Materialize` →
  `materialize.end` lands → cells pulse → activity tab gets the
  lifecycle frames.

## Observation

The previous frontend was three full-page tabs (Records / Dashboard
/ History) — useful as a minimum, but the Daytona-style multi-pane
density that real review work calls for needs an integrated layout.
The handoff bundle is the design we'd been waiting for: it's been
sanded across ten rounds with the user, has a clear identity, and
matches the kind of dense AI-data-tool we want.

## Decision

- **Drop TanStack Table.** Plain HTML tables are simpler, faster on
  the data sizes Folio targets, and exactly what the prototype uses.
  The bundle is 24 KB lighter for it.
- **Keep the contract immutable from the UI.** Spec §19.2 is
  explicit; we don't ship the prototype's column add/edit/delete.
- **Keep direct writes provenance-free for now.** The `human_override`
  log requires extending `upsert_records` / `delete_records` and
  comes with non-trivial test surface. Track separately; the viewer
  layout doesn't depend on it.
- **Source string alignment.** Production uses `human_override`,
  the prototype used `human`. Frontend types track production.

## Permanent Fix

- `make verify` covers the rewrite via the existing pytest cases
  (`test_viewer.py`, `test_viewer_events.py`) and the live SSE
  smoke (`scripts/smoke-viewer.sh`).
- `scripts/harness_check.py` requires every new viewer source file
  so a missed file fails the gate before any UI lands.

## Next Check

If follow-up work adds provenance writes to `upsert_records`, the
existing viewer wiring will start showing `human_override` dots on
edited cells with no further frontend change — the cell
already reads provenance through `getProvenance` and renders the
right dot color.
