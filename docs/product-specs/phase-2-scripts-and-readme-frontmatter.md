# Phase 2 — Reusable Scripts and README Frontmatter

The third executable slice of Folio. Phase 2 turns a Phase 1 sheet
into a self-describing AI-native unit by adding **reusable scripts**
that derivations and humans can invoke, and **README frontmatter**
that surfaces AI-oriented metadata (purpose, usage, default actor,
and a contract pointer) for agents that read sheets without going
through the SDK.

```
my-sheet/
  contract.yaml
  records.jsonl
  derivations/
  scripts/                        # NEW
    enrich-industry.py
    requirements.txt              # optional, language-specific
  README.md                       # YAML frontmatter (NEW) + human docs
  provenance.jsonl
```

The runtime for `scripts/` lives **outside** the sheet under
`<user-cache>/folio/<sheet-id>/runtime/` per ADR-0008.

## In scope

### scripts/

- `src/folio/scripts.py`: discovery + execution helpers.
- Language detection from file extension: `*.py`, `*.js`, `*.sh`
  (Phase 2 ships Python and shell; Node.js detection lands here but
  execution is deferred).
- Execution environment is created on first use and cached at
  `<user-cache>/folio/<sheet-id>/runtime/<lang>/`. Each language
  resolves to a stable command:
  - `python` → `<runtime>/python/.venv/bin/python` if
    `scripts/requirements.txt` is present (managed via `uv`); else
    the project Python.
  - `shell` → `bash` (system).
- `Sheet.run_script(name, args, actor)` executes the script with the
  sheet path as the first argument, captures stdout/stderr, and
  returns `{exit_code, stdout, stderr, duration_seconds}`.
- Scripts are not re-executed by `materialize`; they are invoked
  explicitly. The `python` derivation kind (Phase 4) builds on this
  surface.

### README frontmatter

- `README.md` may begin with a YAML frontmatter block delimited by
  `---`. The rest of the file is human-readable documentation.
- Required fields when a frontmatter block is present:
  - `purpose: <one sentence>` — what the sheet is for.
  - `default_actor: <string>` — fallback actor when the SDK / CLI is
    invoked without one (does **not** override an explicit `--actor`).
- Optional fields:
  - `tags: [...]`
  - `links: { contract: contract.yaml, ... }`
  - `agent_skills: [...]` — pointer to Anthropic Agent Skills
    metadata (alignment is an open issue per design overview
    Appendix B).
- `src/folio/readme.py` parses the frontmatter; `Sheet.metadata`
  exposes it as a typed object.
- `folio validate` surfaces frontmatter issues (missing `purpose`,
  invalid YAML) without blocking unless `--strict` is set.

## Out of scope (deferred to later phases)

- The `python` derivation kind that *calls* a function in `scripts/`.
  Phase 4 (extension kinds).
- Node.js script execution. Re-evaluated when a real consumer
  appears.
- A registry of script signatures (which functions exist, what they
  take). Not introduced until consumers need it.
- Long-running script execution policies (timeouts beyond a fixed
  default, sandboxing). Reopen if production use demands it.

## Verification expectations

- Pydantic v2 frontmatter model with required-field rejection,
  invalid-YAML rejection, and the optional `links` / `tags` shape.
- Python script execution test that creates a temp script, runs it
  through `Sheet.run_script`, asserts the captured stdout, and
  cleans up the runtime cache.
- Shell script execution test for the same flow.
- Path-traversal test: `Sheet.run_script("../bad")` is rejected.
- Runtime cache placement test (mirrors ADR-0008): the runtime
  directory must resolve under `<user-cache>/folio/<sheet-id>/runtime/`.
- A new `scripts-smoke.sh` builds a sheet with one Python script,
  runs it via `folio script run`, and asserts the expected
  exit code and stdout.

## Reference scenario (target behavior)

```bash
$ cat my-sheet/scripts/hello.py
#!/usr/bin/env python3
print("hello from folio")

$ folio script run ./my-sheet hello
{"exit_code": 0, "stdout": "hello from folio\n", "stderr": "", "duration_seconds": 0.04}

$ head -1 my-sheet/README.md
---

$ folio validate ./my-sheet
contract.yaml is valid: my-sheet v1.0.0 (5 fields)
records.jsonl is readable (3 records)
README.md frontmatter is valid (purpose: customer master, default_actor: agent:enrichment)
```

## Suggested implementation breakdown

- **`FOLIO-H-014`**: `src/folio/scripts.py` (discovery + Python and
  shell execution + path-traversal rejection + runtime placement),
  `Sheet.run_script`, `folio script run` CLI verb, deterministic
  shell smoke.
- **`FOLIO-H-015`**: `src/folio/readme.py` (Pydantic v2 frontmatter
  model + parse helpers), `Sheet.metadata`, `folio validate`
  enhancement, frontmatter tests.

## Related

- Canonical specification: [`../design-docs/overview.md`](../design-docs/overview.md) §5, §13.4
- Anthropic Agent Skills (alignment): see open issues in design
  overview Appendix B.
