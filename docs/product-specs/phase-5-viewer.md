# Phase 5 — Viewer

The sixth executable slice of Folio. Phase 5 ships `folio-viewer`, a
local-only web UI that visualizes a sheet, lets humans review the
records that AI agents have populated, and edits the fields that the
contract marks as `x-editable-by`. The Viewer is **read-mostly**: it
never edits `contract.yaml` or `derivations/` (those are file-system
changes per §19.2).

```
folio serve <sheet> --port 3000
```

## In scope

### Architecture

- Backend: FastAPI under `src/folio_viewer/server.py`. Imports the
  SDK directly (no extra protocol layer).
- Frontend: React + TanStack Table + TanStack Virtual under
  `viewer/` (Vite project).
- Communication: REST (primary). SSE (`/events`) for one-way push
  of agent activity (V6).
- Bind: 127.0.0.1 only. CSRF token issued on first GET and
  required on every mutating call. No public deployment posture in
  Phase 5.
- `[project.scripts]` registers `folio-viewer = "folio_viewer.cli:main"`.
- `folio serve` (existing CLI verb in design overview §17) becomes a
  shortcut for `folio-viewer` against the given sheet.

### Stages (per design overview §19.3)

| Stage | Feature |
|---|---|
| V0 | Read-only display of `records.jsonl` |
| V1 | Show types and descriptions from contract |
| V2 | Edit human-editable fields (per `x-editable-by`) |
| V3 | Provenance hover, derivation badges, status colors |
| V4 | Materialize dashboard (per-target counts, last run, run button) |
| V5 | History view (per record × field) |
| V6 | Live agent activity via SSE |

### REST endpoints

One-to-one mapping with SDK operations (per §19.4):

```
GET  /api/contract
GET  /api/records?filter=&fields=&limit=&cursor=
GET  /api/records/{id}?fields=
POST /api/records              # upsert
DELETE /api/records?ids=
POST /api/query                # body: {sql, params}
GET  /api/status?targets=
POST /api/materialize          # body: {targets, record_ids, force, actor}
GET  /api/provenance?record_id=&field=&history=
GET  /events                   # SSE
```

CSRF token requirement on `POST` / `DELETE`.

## Out of scope (deferred to later phases)

- Authentication / multi-user. Phase 7 (multi-user, hosted).
- Tauri-based desktop binary. Phase 7.
- Editing `contract.yaml` or `derivations/` from the UI. Spec
  decision: contract changes go through file edits.
- Real-time collaborative editing (CRDT). Out of scope per §14.3.
- Mobile-optimized layout. Phase 5 targets desktop first.

## Verification expectations

- Backend integration tests against a temp sheet covering each REST
  route's success and a representative error path.
- A `viewer-smoke.sh` that:
  - Starts `folio-viewer --port <random>` against a stubbed
    `AIClient` (so `materialize` works offline),
  - Polls `/api/contract`, `/api/records`, and a `POST
    /api/materialize` round trip via `curl`,
  - Asserts the expected JSON shape and exit codes,
  - Tears the server down.
- Frontend: lightweight Playwright test (or equivalent) that boots
  the dev server, loads the records grid, and asserts type
  decorations from V1 are visible.

## Reference scenario (target behavior)

```
$ folio serve ./customers --port 3000
folio-viewer: serving customers on http://127.0.0.1:3000
```

Visiting `http://127.0.0.1:3000/` shows the records table with type
chips, provenance badges (`ai`, `import`, `human`), and an inline
edit affordance on fields whose `x-editable-by` matches the configured
actor.

## Suggested implementation breakdown

- **`FOLIO-H-024`**: V0–V3. FastAPI backend, contract / records /
  query / get_record / provenance routes, React + TanStack scaffold,
  type-decorated grid, provenance hover, derivation badges, edit
  affordance for human-editable fields, CSRF-token plumbing, and the
  backend smoke.
- **`FOLIO-H-025`**: V4–V6. Materialize dashboard backed by a
  stubbed `AIClient` for tests, history view, SSE event stream,
  Playwright frontend smoke. The `folio serve` CLI alias lands here.

## Related

- Canonical specification: [`../design-docs/overview.md`](../design-docs/overview.md) §15, §19
- Library selection (TanStack, FastAPI): §20
