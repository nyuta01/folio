#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-python3}"

echo "== workspace =="
pwd

echo
echo "== recent commits =="
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  git log --oneline -5
else
  echo "(no commits yet)"
fi

echo
echo "== working tree =="
git status --short

echo
echo "== handoff =="
sed -n '1,220p' AGENT_PROGRESS.md

echo
echo "== harness check =="
"$PYTHON" scripts/harness_check.py

echo
echo "== drift check =="
"$PYTHON" scripts/harness_drift.py

echo
echo "== verify =="
make verify
