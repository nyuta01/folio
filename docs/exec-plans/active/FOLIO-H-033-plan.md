# FOLIO-H-033 Plan: Harden contract.yaml Atomic Writes

## Goal

Remove the symlink-clobber vulnerability in `write_contract()` where schema
mutation paths wrote through the predictable `contract.yaml.tmp` filename
before renaming it over `contract.yaml`.

## Scope

- `src/folio/contract.py`: replace the predictable temp path with an
  exclusive random temp file created in the sheet directory, fsynced before
  publishing with `os.replace()`.
- `tests/test_contract.py`: add a regression test proving a malicious
  `contract.yaml.tmp` symlink is ignored and the victim file is not clobbered.
- `scripts/harness_drift.py`: reject future reintroduction of predictable
  contract temp names or symlink-following `Path.write_text` in the contract
  writer.
- Docs and PDCA artifacts: record the security-sensitive filesystem failure
  and its permanent checks.

## Out of Scope

- Changing the Viewer or SDK property mutation API semantics.
- Removing arbitrary extra files from sheet directories; portability rules
  already allow plain files, and the vulnerability is fixed by never writing
  through attacker-chosen temp paths.

## Evidence

- `uv run pytest tests/test_contract.py tests/test_viewer.py -q` passes.
- `make verify` passes.

## Observation

Aardvark reported that `write_contract()` built a fixed `contract.yaml.tmp`
path and used `Path.write_text()`. Because that API follows symlinks, a
malicious sheet could pre-create `contract.yaml.tmp` as a symlink to a
user-writable victim file, then trigger schema editing through the SDK or
Viewer to overwrite that victim with serialized contract YAML.

## Decision

Use `tempfile.mkstemp()` with a hidden `.contract.*.yaml.tmp` prefix in the
sheet directory, write and fsync the already-open exclusive file descriptor,
and publish with `os.replace()`. This preserves same-directory atomic replace
semantics while avoiding all attacker-controlled predictable temp paths.

## Permanent Fix

`tests/test_contract.py::test_contract_write_ignores_predictable_tmp_symlink`
creates a sheet-local `contract.yaml.tmp` symlink to a victim file, performs a
schema mutation through `open_sheet(...).add_property(...)`, and asserts the
victim stays unchanged, the canonical `contract.yaml` is not a symlink, and the
new property is persisted. `make drift-check` also fails if the contract writer
returns to a predictable `.yaml.tmp` suffix or direct `Path.write_text` sink.

## Next Check

Keep contract and records writers aligned: any future sheet-file atomic writer
must use exclusive random temp files in the target directory and a regression
test for symlink pre-creation before it is exposed through SDK or Viewer
mutation routes.
