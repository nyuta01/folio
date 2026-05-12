# Agent Failures

Append-only log for repeated or high-impact agent process failures.

Status values:

- `observing`
- `needs-fix`
- `fixed`
- `archived`
- `fixed-but-regressing`

## F-001 Mutable release assets trusted for PyPI publishing

- **Status**: `fixed`
- **Task**: `FOLIO-H-028`
- **Plan**: `docs/exec-plans/active/FOLIO-H-028-plan.md`

### Observation

The Release-published PyPI OIDC job trusted mutable GitHub Release assets and
embedded the release tag in a shell command, creating a supply-chain path for a
release editor or compromised release process to upload untrusted wheel/sdist
files.

### Permanent fix

`.github/workflows/release-python.yml` now rebuilds and smoke-tests from the
release tag during the release-published workflow run, then `publish-pypi`
downloads only same-run artifacts with `actions/download-artifact`.
`scripts/harness_drift.py` rejects future PyPI publish paths that call
`gh release download`, omit the build dependency, skip release-event builds, or
interpolate release tag expressions into publish-job shell snippets.

## F-002 Desktop agent PATH hijack from sheet `.venv`

- **Status**: `fixed`
- **Task**: `FOLIO-H-029`
- **Plan**: `docs/exec-plans/active/FOLIO-H-029-plan.md`

### Observation

Desktop chat agent execution trusted `.venv/bin` paths derived from the opened
sheet. A malicious portable sheet could include `.venv/bin/folio` as a marker
and `.venv/bin/claude` as a payload, causing Folio Desktop to execute
sheet-provided code when the user started a chat turn.

### Permanent fix

`runAgent` no longer mutates `PATH` from sheet-controlled locations and resolves
the trusted agent executable from the host PATH before spawning with the sheet
as cwd. `scripts/harness_drift.py` rejects future direct PATH mutation in
`apps/desktop/src/main/agents.ts`.
