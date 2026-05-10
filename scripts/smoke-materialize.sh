#!/usr/bin/env bash
# Deterministic smoke for the Phase 1 materialize loop.
#
# Drives a temporary sheet through the SDK with StubAIClient, asserting
# the §23.3 customer-enrichment scenario from the design overview. No
# live API key required.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

UV="${UV:-uv}"

"$UV" run --frozen python scripts/_materialize_smoke.py
