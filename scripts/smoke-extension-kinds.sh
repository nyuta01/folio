#!/usr/bin/env bash
# Deterministic offline smoke for the Phase 4 sql + http extension kinds.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

UV="${UV:-uv}"

"$UV" run --frozen python scripts/_extension_kinds_smoke.py
