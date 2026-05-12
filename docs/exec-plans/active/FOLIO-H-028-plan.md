# FOLIO-H-028 Plan: Harden PyPI release publishing provenance

## Goal

Remediate the release workflow vulnerability by ensuring PyPI trusted
publishing never uploads mutable GitHub Release assets and never interpolates a
release tag name into a publish-job shell command.

## Scope

- `.github/workflows/release-python.yml` - keep the release-published PyPI
  automation, but rebuild and smoke-test from the release tag during the same
  workflow run and publish only that run's uploaded artifact.
- `scripts/harness_drift.py` - add a deterministic workflow invariant that
  rejects `gh release download` in the PyPI publishing path and requires the
  publish job to depend on the build job plus `actions/download-artifact`.
- `docs/methodology/release.md` - document the safe publish path for release
  operators.
- Project state artifacts - record the security permanent fix.

## Out of Scope

- Desktop release signing, notarization, or artifact provenance changes.
- Changing PyPI trusted-publishing configuration outside the repository.

## Observation

The `release: published` workflow path gave the PyPI job OIDC publishing
authority while skipping the build-and-smoke job. It filled `dist/` from
mutable GitHub Release assets with `gh release download` and embedded
`github.event.release.tag_name` directly in the publish-job shell script.
That broke provenance between source at the release tag and the package sent
to PyPI.

## Decision

Keep the operator-friendly "publish the draft Release" trigger, but make that
event start a fresh trusted build from the release tag. The `publish-pypi` job
now depends on `build-and-release`, downloads the wheel and sdist from the same
workflow run's artifact store, and uploads that directory to PyPI. Release
assets remain user-facing downloads only, not PyPI inputs.

## Permanent Fix

`scripts/harness_drift.py` now enforces the release workflow invariant: PyPI
publishing must not call `gh release download`, must depend on
`build-and-release`, must use `actions/download-artifact`, must not skip the
release event build, and must not leave release tag expressions in
publish-job shell snippets. `make verify` runs this check through
`make drift-check`.

## Next Check

If future release work changes `.github/workflows/release-python.yml`, run
`make drift-check` before review and verify that the PyPI path still publishes
only same-run build artifacts.
