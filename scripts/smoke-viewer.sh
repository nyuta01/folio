#!/usr/bin/env bash
# Deterministic smoke for the Phase 5 Viewer backend (V0–V3).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

UV="${UV:-uv}"

"$UV" run --frozen python scripts/_viewer_smoke.py
