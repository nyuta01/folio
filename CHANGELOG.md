# Changelog

All notable user-facing changes. The format roughly follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the public API is alpha (`0.x`), minor bumps may include
breaking changes.

Each release ships three artifact families: a Python distribution on
PyPI as `folio-kit`, desktop apps (DMG / NSIS / AppImage / deb) on the
GitHub Release, and (separately versioned) the `folio-agent-skills`
npm package.

## [Unreleased]

— Nothing yet.

## [0.1.7] — 2026-05-11

### Added

- **Per-sheet skills** — a sheet can ship packaged operating
  procedures as markdown files under `<sheet>/skills/<name>.md`.
  Each file is a short YAML-frontmatter + prose document
  (`name`, `description`, optional `audience`, `arguments`,
  `tools`, `allowed_actors`); the body is plain markdown with
  `{arg}` placeholder substitution. Skills travel with the sheet
  tarball, so a `tar`-extracted sheet brings its operating manual
  along.
- **`Skill` model + SDK**: `folio.Skill`, `folio.SkillArgument`,
  `folio.SkillError`, `folio.load_skills`,
  `folio.validate_skills_manifest`, `folio.export_claude_skills`.
  `Sheet.list_skills()`, `Sheet.get_skill(name)`,
  `Sheet.render_skill(name, args)` on every opened sheet.
- **`folio skill` CLI sub-app**: `folio skill list <sheet>`,
  `folio skill show <sheet> <name> [--arg name=value]`,
  `folio skill validate <sheet>`.
- **MCP prompts**: the Folio MCP server now registers one prompt
  per discovered skill under each sheet, named
  `<sheet-id>:<skill-name>`. Skill arguments surface as prompt
  argument schemas; `prompts/get` renders the markdown body with
  substitutions.
- **`folio export claude-skills`**: bridge that emits one
  `SKILL.md` directory per skill in the layout Claude Code expects,
  for projects that want skills surfaced inside Claude Desktop /
  Claude Code as well as MCP.
- **Five example skills** — one per `examples/` sheet
  (`fill-missing-industries`, `refresh-revenue`,
  `advance-onboarding`, `triage-candidates`, `weekly-digest`).
- **Docs**: new `sheet/skills/` and `cli/skill/` pages on the docs
  site.

### Changed

- `Sheet.contract.id` is now used as the MCP prompt namespace
  prefix to avoid skill-name collisions when one server hosts
  multiple sheets.

## [0.1.6] — 2026-05-11

Pre-public-release audit fixes. No behavioural changes; the wheel
and SDK are identical in shape to 0.1.5.

### Added

- **`LICENSE`** at the repo root, in the PyPI sdist + wheel, and in
  the `folio-agent-skills` npm pack. MIT was declared in metadata
  but no license text was shipped — now it is.
- **`SECURITY.md`** with private vulnerability-reporting channels.
- **`CONTRIBUTING.md`** with the `make verify` quick start.
- **`CODE_OF_CONDUCT.md`** (Contributor Covenant 2.1).
- **`.github/`** scaffolding: issue templates (bug, feature),
  PR template, `CODEOWNERS`, `dependabot.yml` covering Python +
  every npm workspace + GitHub Actions.

### Fixed

- **Desktop app install hint** — the "folio-viewer not found"
  error dialog now recommends `pipx install folio-kit`. Previous
  versions recommended `pipx install folio`, which is an unrelated
  abandoned 2014 PyPI package.
- **Docs site stale CLI flags** — `apps/docs/src/content/docs/cli/`
  `materialize.mdx` and `status.mdx`, plus
  `get-started/materialize-lifecycle.mdx`, documented `--target` and
  `--record-ids` flags that don't exist. Corrected to the real
  positional-target + `--ids` syntax. Same class of bug as the
  `folio-agent-skills@0.1.1` SKILL.md fix.
- **README sheet count** — README.md said "four use-case sheets" but
  `examples/` ships five (the customer-revenue sidecar was missed).
- **`docs/methodology/release.md`** — `folio-X.Y.Z-py3-none-any.whl`
  → `folio_kit-X.Y.Z-py3-none-any.whl` (rename leftover).
- **`apps/docs/package.json`** bumped to match other manifests.
- **`.gitignore`** widened to cover `apps/desktop/out/`,
  `viewer/dist/`, `apps/docs/dist/`, `*.log`, `coverage/`, `.turbo/`.

### Changed

- **`scripts/bump-version.sh`** now also updates `apps/docs/package.json`
  so every manifest in the monorepo moves together.

## `folio-agent-skills` [0.1.1] — 2026-05-11

### Fixed

- Corrected stale CLI flag references in three SKILL.md files:
  `folio materialize` takes the derivation target as a *positional*
  argument (not `--target`) and filters by `--ids` (not
  `--record-ids`); `folio provenance` takes record ID + field as
  positional arguments (not `--record-id` / `--field`);
  `folio list` filters by `--filter "id = ?" --param <id>` (no
  `--record-ids` flag). Discovered during an end-to-end smoke against
  `folio-kit==0.1.5`.

## [0.1.4] — 2026-05-11 (PyPI-only)

A transient release published to PyPI during the `folio` → `folio-kit`
rename. No git tag exists for this version — only the wheel + sdist
on PyPI, which were superseded the same day by `0.1.5`. Users should
install `folio-kit>=0.1.5`.

## [0.1.5] — 2026-05-11

### Added

- **`folio-agent-skills` npm package (0.1.0)** — first publish of the
  distributable agent-skills pack. Four `SKILL.md` files
  (`folio-quickstart`, `add-derivation-ai`, `add-derivation-cross-sheet`,
  `debug-failed-materialize`) installable via
  `npx skills add nyuta01/folio` (skills.sh ecosystem) or as a TanStack
  Intent-indexed npm dependency.
- **Distributable Folio Skills source tree** at `skills/` with
  `.claude-plugin/marketplace.json` and `package.json` so the same
  source feeds Claude plugins, skills.sh, and TanStack Intent.
- **PyPI Trusted Publisher (OIDC)** wired into `release-python.yml`:
  publishing now flows through a dedicated `publish-pypi` job with
  `environment: pypi`.
- **`README.pypi.md`** — focused, user-facing description shown on
  PyPI. Drops contributor-only material (apps/docs build steps,
  `make agent-init`, ADR links) from the package description.

### Changed

- **PyPI distribution renamed** from `folio` to `folio-kit`. The
  `folio` name on PyPI was held by an abandoned 2014 package. The
  on-disk command stays `folio`; only the install argument changes
  (`pipx install folio-kit`). All documentation updated accordingly.
- **Version sync across packages.** `pyproject.toml`,
  `apps/desktop/package.json`, and `viewer/package.json` are now
  expected to share the same version so GitHub Release assets are
  labelled consistently.

### Fixed

- Mixed-version GitHub Release filenames (Python `0.1.5` alongside
  desktop `0.1.3`) were resolved by syncing desktop / viewer
  `package.json` versions to match `pyproject.toml`.

## [0.1.3] — 2026-05-10

### Added

- **"Locate folio-viewer…" picker** in the desktop app for non-standard
  Python installations (e.g. virtualenvs whose `bin/` isn't on the
  shell `$PATH`). Picked path is persisted as a per-user setting.
- **`SPECIFICATION.md`** at the repo root — single externally-publishable
  contract covering every wire format, derivation kind, lifecycle, and
  MCP tool. Drift is gated by `make verify-spec`.

### Fixed

- Desktop app no longer crashes silently with `spawn folio-viewer
  ENOENT`. Server-manager now installs an early `error` listener,
  augments `PATH` with the user's interactive-shell value, probes
  pipx / uv tool install candidate paths, and falls back to a file
  dialog.
- macOS Gatekeeper warning ("Apple cannot verify…") is documented in
  the README with the `xattr -dr com.apple.quarantine` workaround
  while code signing remains pending.
- Python sdist size — trimmed `[tool.hatch.build.targets.sdist]
  include` to the project surface so `apps/desktop/out/` and
  `viewer/dist/` no longer sweep into the tarball.

## [0.1.2] — 2026-05-10

### Fixed

- `folio-viewer` discovery from a packaged macOS `.app`. The
  desktop launcher's `PATH` is sparse (no shell rcfiles loaded), so
  the runtime now probes a fixed candidate list (`~/.local/bin/`,
  `/opt/homebrew/bin/`, `/usr/local/bin/`, the bundled env).

## [0.1.1] — 2026-05-10

### Added

- Release pipeline scaffolding: `release-python.yml`,
  `release-desktop.yml`, `release-docs.yml`, plus the artifact upload
  conventions still in use.

## [0.1.0] — 2026-05-10

### Added

- Initial public alpha. Core wire formats (`contract.yaml`,
  `records.jsonl`, `provenance.jsonl`), six derivation kinds (`ai`,
  `python`, `sql`, `cross_sheet`, `import`, `http`), CLI verbs,
  Python SDK, FastMCP server, viewer backend, and the macOS / Windows /
  Linux Electron viewer app.

[Unreleased]: https://github.com/nyuta01/folio/compare/v0.1.7...HEAD
[0.1.7]: https://github.com/nyuta01/folio/releases/tag/v0.1.7
[0.1.6]: https://github.com/nyuta01/folio/releases/tag/v0.1.6
[0.1.5]: https://github.com/nyuta01/folio/releases/tag/v0.1.5
[0.1.4]: https://pypi.org/project/folio-kit/0.1.4/
[0.1.3]: https://github.com/nyuta01/folio/releases/tag/v0.1.3
[0.1.2]: https://github.com/nyuta01/folio/releases/tag/v0.1.2
[0.1.1]: https://github.com/nyuta01/folio/releases/tag/v0.1.1
[0.1.0]: https://github.com/nyuta01/folio/releases/tag/v0.1.0
