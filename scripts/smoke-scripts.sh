#!/usr/bin/env bash
# Deterministic smoke for the Phase 2 reusable-script runtime.
#
# Builds a temporary sheet with one Python and one shell script,
# runs them via the folio CLI, and asserts the captured stdout.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

UV="${UV:-uv}"

SHEET_DIR="$(mktemp -d -t folio-scripts-smoke.XXXXXX)"
trap 'rm -rf "$SHEET_DIR"' EXIT

cat > "$SHEET_DIR/contract.yaml" <<'EOF'
apiVersion: v3.0.0
kind: DataContract
id: scripts-smoke
name: scripts-smoke
version: 1.0.0
schema:
  - name: items
    physicalType: jsonl
    properties:
      - name: id
        logicalType: string
        primaryKey: true
        required: true
EOF
: > "$SHEET_DIR/records.jsonl"

mkdir "$SHEET_DIR/scripts"
cat > "$SHEET_DIR/scripts/hello.py" <<'EOF'
import sys
print(f"hello sheet={sys.argv[1]} args={sys.argv[2:]}")
EOF

cat > "$SHEET_DIR/scripts/echo.sh" <<'EOF'
#!/usr/bin/env bash
echo "echo sheet=$1 args=${*:2}"
EOF
chmod +x "$SHEET_DIR/scripts/echo.sh"

folio() {
  "$UV" run --frozen folio "$@"
}

LIST_JSON="$(folio script list "$SHEET_DIR")"
case "$LIST_JSON" in
  *'"name": "hello"'*'"name": "echo"'* | *'"name": "echo"'*'"name": "hello"'*) ;;
  *)
    echo "smoke-scripts: list missing names; got $LIST_JSON" >&2
    exit 1
    ;;
esac

PY_JSON="$(folio script run "$SHEET_DIR" hello one two --timeout 10)"
case "$PY_JSON" in
  *'"exit_code": 0'*'hello sheet='*"args=['one', 'two']"*) ;;
  *)
    echo "smoke-scripts: python run mismatch; got $PY_JSON" >&2
    exit 1
    ;;
esac

SH_JSON="$(folio script run "$SHEET_DIR" echo alpha beta --timeout 10)"
case "$SH_JSON" in
  *'"exit_code": 0'*'echo sheet='*'args=alpha beta'*) ;;
  *)
    echo "smoke-scripts: shell run mismatch; got $SH_JSON" >&2
    exit 1
    ;;
esac

# Unknown script must exit non-zero.
if folio script run "$SHEET_DIR" ghost --timeout 5 >/dev/null 2>&1; then
  echo "smoke-scripts: ghost script should fail" >&2
  exit 1
fi

echo "smoke-scripts: ok"
