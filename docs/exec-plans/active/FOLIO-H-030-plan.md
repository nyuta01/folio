# FOLIO-H-030 Plan: Confine Desktop Agent Cwd

## Goal

Remediate the Desktop chat-agent IPC vulnerability where renderer JavaScript
could provide an arbitrary working directory for a coding-agent spawn. Agents
must run only in the sheet directory selected and tracked by the Electron main
process.

## Scope

- `apps/desktop/src/main/main.ts` - ignore any renderer-supplied `cwd` on
  `agents:run`; derive the spawn directory exclusively from `currentSheet` and
  fail clearly when no sheet is open.
- `apps/desktop/src/preload/preload.cjs` - stop forwarding the raw renderer
  payload for `agents.run`, keeping `cwd` out of the preload-facing API shape.
- `viewer/src/folio-bridge.d.ts` - remove `cwd` from the typed renderer bridge
  contract.
- `scripts/harness_drift.py` - add a deterministic guard that rejects future
  regressions where the agent IPC handler or bridge re-exposes
  renderer-chosen cwd.
- Update the design overview, execution plan, quality score, failure log, and
  progress handoff artifacts.

## Out of Scope

- Changing chat UI behavior; the UI already omits `cwd`.
- Replacing the preload bridge with a full sender/origin authorization layer.
- Changing the Desktop server binding or Viewer REST API.

## Observation

The Electron preload exposed `agents.run(payload)`, and the main-process
`agents:run` handler trusted `payload.cwd` when spawning the configured coding
agent. The React UI did not send `cwd`, but renderer code is not a security
boundary: XSS or otherwise attacker-controlled renderer JavaScript could run
the configured agent outside the selected sheet while inheriting the desktop
process environment.

## Decision

Keep the powerful process-spawn primitive in the Electron main process and
make the selected sheet path a main-process authority. The renderer may choose
agent id, prompt, session id, and follow-up state, but it may not choose the
filesystem working directory. A missing current sheet is a hard error instead
of falling back to renderer input.

## Permanent Fix

`scripts/harness_drift.py` now checks that Desktop agent IPC derives cwd from
`currentSheet`, never references `p.cwd` / `payload.cwd`, does not forward a
raw preload payload to `agents:run`, and keeps `cwd` out of the renderer bridge
type. This turns the vulnerability pattern into a deterministic drift failure.

## Next Check

Run `make verify`, Desktop TypeScript checks, and a targeted runtime IPC check
before merging. Future Desktop-agent work should add any new renderer-exposed
process-spawn fields to this same drift invariant or replace it with a focused
Desktop IPC security test suite if one is introduced.
