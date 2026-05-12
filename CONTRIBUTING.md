# Contributing to Folio

Thanks for considering a contribution. This guide covers the basics
of working on the repo.

## Quick start

```bash
git clone https://github.com/nyuta01/folio.git
cd folio
make sync               # installs Python deps into .venv via `uv sync`
make verify             # the single deterministic gate (~10s)
```

If `make verify` is green on a clean checkout, your environment is
healthy. If it isn't, please open an issue with the output rather
than masking it.

## The verification gate

`make verify` runs, in order:

| Stage | What it checks |
|---|---|
| `harness-check` | Repo harness shape + structured task state |
| `drift-check` | Plan / failure-log drift invariants |
| `validate-docs` | Design doc + ADR structure + docs-local links |
| `verify-spec` | `SPECIFICATION.md` matches the live implementation |
| `python-test` | Pytest unit tests |
| `cli-smoke` … `viewer-smoke` | Five end-to-end smokes (CLI, materialize, scripts, extension kinds, viewer) |

Every change must keep all of these green. If you can't run one
locally (e.g. you don't have `npm` for the viewer smoke), say so in
the PR description — CI will re-run them anyway.

## Branching & PRs

- Branch off `main`. Use a descriptive branch name (e.g.
  `derivation-http-headers`, not `fix-1`).
- Open a draft PR early. The PR template asks for a one-line
  rationale + the test plan.
- Keep PRs focused. If a refactor and a bug fix overlap, split them.

## Code style

- **Python**: 3.13+, type hints, prefer `pathlib` over raw strings,
  `pydantic` models for any cross-module data shape.
- **TypeScript**: strict mode, no `any`, prefer named exports.
- **Comments**: write *why*, not *what*. Code should explain itself;
  comments earn their keep when context is non-obvious.
- **No emoji** in source files unless the user-facing copy genuinely
  needs them.

## Adding a new derivation kind

This is a common contribution. The path is:

1. Add the kind to `_kinds.py` and register in `_runtime.py`.
2. Add a YAML schema fragment to the contract loader.
3. Add a smoke under `scripts/smoke-*.sh` that runs the kind
   against a tiny fixture sheet.
4. Document it under `apps/docs/src/content/docs/sheet/derivations/`.
5. Add a row to `SPECIFICATION.md`.
6. Bump `make verify-spec`'s expectation table — drift fails CI.

## Versioning

All four version manifests must move together:

```bash
make bump-version VERSION=0.1.X
```

This updates `pyproject.toml`, `apps/desktop/package.json`,
`viewer/package.json`, and `uv.lock`. Do not edit them by hand.

The `folio-agent-skills` npm package under `skills/` is versioned
independently.

## Reporting bugs

Use the GitHub issue templates. Include:

- `folio --version` (or commit hash) and OS
- Minimal reproducer (a small sheet directory + the exact command)
- Expected vs actual

## Releases

Releases happen from `main`. See `docs/methodology/release.md` for
the full procedure. Triggering a release is a maintainer action.

## License

By contributing you agree that your contributions are licensed
under the MIT license that covers the rest of the project.
