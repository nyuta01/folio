#!/usr/bin/env bash
# Deterministic smoke for the Phase 3 MCP server.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

UV="${UV:-uv}"

"$UV" run --frozen python scripts/_mcp_smoke.py
