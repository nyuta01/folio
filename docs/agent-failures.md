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

## F-003 Renderer-controlled Desktop agent cwd

- **Status**: `fixed`
- **Task**: `FOLIO-H-030`
- **Plan**: `docs/exec-plans/active/FOLIO-H-030-plan.md`

### Observation

Renderer JavaScript could call the Electron `agents:run` IPC path with an
arbitrary `cwd`, causing the main process to spawn a coding agent outside the
selected sheet while inheriting the Desktop process environment.

### Permanent fix

The main-process handler ignores renderer cwd fields and derives cwd only from
`currentSheet`; the preload no longer forwards arbitrary run payloads; the
renderer bridge type omits cwd; `scripts/harness_drift.py` now fails if the cwd
field is re-exposed or consumed again.

## F-004 Unauthenticated MCP HTTP remote-agent guidance

- **Status**: `fixed`
- **Task**: `FOLIO-H-031`
- **Plan**: `docs/exec-plans/active/FOLIO-H-031-plan.md`

### Observation

User-facing docs showed `folio-mcp` HTTP bound to all interfaces for remote
agents. The underlying server had no built-in authentication, so operators
following that recipe could expose sheet read/write/delete/materialize tools to
any reachable client under the configured `--root`.

### Permanent fix

The MCP server surface was removed rather than retained with safer prose:
`folio-mcp`, `src/folio_mcp`, FastMCP, MCP docs, MCP tests, and `mcp-smoke` are
gone. `scripts/harness_drift.py` rejects reintroducing the package, docs,
dependency, console script, or smoke target.

## F-005 DuckDB SELECT-only was not filesystem-sandboxed

- **Status**: `fixed`
- **Task**: `FOLIO-H-032`
- **Plan**: `docs/exec-plans/active/FOLIO-H-032-plan.md`

### Observation

`Sheet.query` rejected write-leading SQL but still allowed SELECT statements to
call DuckDB external file functions such as `read_text`, exposing files
readable by the Folio process.

### Permanent fix

`src/folio/_query.py` now loads `records.jsonl` through Python into an
in-memory DuckDB table and connects with `enable_external_access=false`;
`tests/test_sheet.py::test_query_cannot_read_files_outside_sheet` guards the
exploit path. Any future query, SQL derivation, or DuckDB extension work must
preserve that external-access sandbox.

## F-006 Predictable contract temp path followed sheet symlinks

- **Status**: `fixed`
- **Task**: `FOLIO-H-033`
- **Plan**: `docs/exec-plans/active/FOLIO-H-033-plan.md`

### Observation

A schema-editing implementation added `write_contract()` with a predictable
`contract.yaml.tmp` path and `Path.write_text()`. Because that write follows
symlinks, an attacker-controlled sheet could include `contract.yaml.tmp` as a
symlink to a user-writable victim file and cause SDK or Viewer schema edits to
clobber the victim with serialized contract YAML.

### Permanent fix

`write_contract()` now uses `tempfile.mkstemp()` to create an exclusive random
same-directory `.contract.*.yaml.tmp` file, writes and fsyncs the open file
descriptor, publishes with `os.replace()`, and removes the random temp file on
failure. `tests/test_contract.py::test_contract_write_ignores_predictable_tmp_symlink`
pre-creates the malicious predictable symlink and verifies a schema mutation
does not alter the victim or turn `contract.yaml` into a symlink. `make drift-check`
rejects reintroducing the predictable temp name or direct `Path.write_text`
sink in `write_contract()`.

## F-007 Viewer query route lacked direct sandbox regressions

- **Status**: `fixed`
- **Task**: `FOLIO-H-034`
- **Plan**: `docs/exec-plans/active/FOLIO-H-034-plan.md`

### Observation

Viewer `POST /api/query` exposes `Sheet.query` over HTTP. The root DuckDB
file-read primitive was fixed in `FOLIO-H-032`, but the Viewer route lacked a
direct HTTP regression and the query guard still allowed stacked statements
after a leading SELECT.

### Permanent fix

`Sheet.query` now rejects stacked SQL statements before execution.
`tests/test_viewer.py::test_query_sandbox_blocks_external_file_reads` posts a
DuckDB `read_csv(<outside file>)` query to `/api/query` and asserts the secret
contents are not returned. `scripts/harness_drift.py` rejects removal of the
query sandbox ingredients or the Viewer HTTP regression.
