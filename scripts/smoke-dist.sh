#!/usr/bin/env bash
# Smoke-test the freshly-built wheel by installing it into a throwaway venv
# and asserting the three console scripts run.
#
# Run from the repo root: bash scripts/smoke-dist.sh
# (Usually invoked via `make dist-check`.)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEEL="$(ls "${REPO_ROOT}/dist"/folio_kit-*.whl 2>/dev/null | head -n 1)"

if [[ -z "${WHEEL}" ]]; then
  echo "smoke-dist: no wheel under dist/ — run \`make dist\` first" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

echo "smoke-dist: installing ${WHEEL##*/} into ${TMP}/venv"
uv venv "${TMP}/venv" --python 3.13 >/dev/null
uv pip install --quiet --python "${TMP}/venv/bin/python" "${WHEEL}"

echo "smoke-dist: invoking entry points"
"${TMP}/venv/bin/folio" --help >/dev/null
"${TMP}/venv/bin/folio-mcp" --help >/dev/null
"${TMP}/venv/bin/folio-viewer" --help >/dev/null

echo "smoke-dist: ok (folio, folio-mcp, folio-viewer all run from the wheel)"
