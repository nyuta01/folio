# FOLIO-H-029 Plan: Harden Desktop Agent PATH Handling

## Goal

Prevent untrusted Folio sheets from influencing which desktop chat agent
binary the Electron main process executes.

## Scope

- Remove `runAgent` PATH augmentation derived from the opened sheet directory
  or its parents.
- Resolve the trusted agent executable from the host process PATH before
  spawning the child process with the sheet as cwd.
- Keep the existing agent registry and `claude` invocation behavior otherwise
  unchanged.
- Add a deterministic drift check that rejects future desktop agent PATH
  mutation in `apps/desktop/src/main/agents.ts`.
- Record the security failure and update quality / handoff artifacts.

## Out of Scope

- Changing the renderer chat UI.
- Adding a desktop installer preference screen for explicit agent binary paths.
- Changing `main.ts` startup PATH augmentation from the user's login shell;
  that remains host-controlled app startup behavior, not sheet-controlled
  runtime behavior.

## Observation

The Desktop `runAgent` path derived `.venv/bin` candidates from the opened
sheet directory, prepended the first marker directory containing `folio` to
`PATH`, and then spawned the bare agent command `claude`. Because Node resolves
bare commands with the supplied environment, an untrusted sheet could provide
`.venv/bin/folio` as the marker and `.venv/bin/claude` as the payload. Starting
a chat turn would execute the sheet-provided binary with the user's desktop
privileges.

## Decision

Treat desktop chat agents as trusted host tools rather than sheet-provided
executables. Resolve the agent binary from the app's inherited host PATH before
the child process cwd changes to the sheet, then spawn that resolved path with
an unmodified environment. Packaged installs and source checkouts must arrange
PATH before launching Folio Desktop.

## Permanent Fix

`apps/desktop/src/main/agents.ts` no longer mutates `PATH` from the opened
sheet. `scripts/harness_drift.py` fails the repository gate if desktop agent
code reintroduces direct PATH mutation, turning this high-impact security issue
into a deterministic check.

## Next Check

If Desktop adds more local-tool conveniences, route them through explicit
trusted install configuration rather than inferring executable directories from
portable sheet contents. Run `make verify` and the Desktop TypeScript build
checks before merging.
