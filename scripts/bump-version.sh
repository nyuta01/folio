#!/usr/bin/env bash
# Bump the shared `0.1.x`-style version across every package manifest in
# this repo. Versions live in three places and must agree, otherwise
# GitHub Release filenames diverge across the Python wheel and the
# Electron desktop builds (see CHANGELOG entry for 0.1.5).
#
# Usage:
#   bash scripts/bump-version.sh 0.1.6
#
# Updates:
#   pyproject.toml                  (project.version)
#   apps/desktop/package.json       (used by electron-builder for artifact names)
#   viewer/package.json             (kept in sync; surfaced in `folio-viewer --help` later)
#
# Then refreshes uv.lock so `uv sync --frozen` in CI keeps working.
# Does NOT commit, tag, or push — review the diff first.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: bash scripts/bump-version.sh <new-version>" >&2
  exit 2
fi

NEW="$1"
if ! [[ "${NEW}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]; then
  echo "bump-version: '${NEW}' does not look like semver" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CURRENT="$(awk -F'"' '/^version = / { print $2; exit }' pyproject.toml)"
echo "bump-version: ${CURRENT} -> ${NEW}"

# pyproject.toml — only the top-level [project] version line.
sed -i.bak -E "1,/^version = /s/^version = \"${CURRENT}\"\$/version = \"${NEW}\"/" pyproject.toml
rm pyproject.toml.bak

# apps/desktop/package.json + viewer/package.json — the first "version": "..." key.
for f in apps/desktop/package.json viewer/package.json; do
  sed -i.bak -E "s/\"version\": \"${CURRENT}\"/\"version\": \"${NEW}\"/" "${f}"
  rm "${f}.bak"
done

# Refresh uv.lock so the workspace member version moves with us.
uv lock >/dev/null

echo "bump-version: updated"
echo "  pyproject.toml             $(awk -F'"' '/^version = / { print $2; exit }' pyproject.toml)"
echo "  apps/desktop/package.json  $(grep -m1 '"version"' apps/desktop/package.json | sed -E 's/.*"version": "([^"]+)".*/\1/')"
echo "  viewer/package.json        $(grep -m1 '"version"' viewer/package.json | sed -E 's/.*"version": "([^"]+)".*/\1/')"
echo
echo "Next: review with 'git diff', then commit + tag:"
echo "  git add pyproject.toml apps/desktop/package.json viewer/package.json uv.lock"
echo "  git commit -m \"Bump to ${NEW}\""
echo "  git tag -a v${NEW} -m \"v${NEW}\""
echo "  git push origin main v${NEW}"
