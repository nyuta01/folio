#!/usr/bin/env bash
# Deterministic smoke for the folio CLI.
#
# Builds a temporary sheet, runs every Phase 0 verb, and asserts the
# expected exit codes and output. Hooked into `make verify` via cli-smoke.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

UV="${UV:-uv}"

SHEET_DIR="$(mktemp -d -t folio-smoke.XXXXXX)"
trap 'rm -rf "$SHEET_DIR"' EXIT

cat > "$SHEET_DIR/contract.yaml" <<'EOF'
apiVersion: v3.0.0
kind: DataContract
id: cli-smoke
name: cli-smoke
version: 1.0.0
schema:
  - name: items
    physicalType: jsonl
    properties:
      - name: id
        logicalType: string
        primaryKey: true
        required: true
      - name: title
        logicalType: string
        required: true
      - name: count
        logicalType: integer
EOF
: > "$SHEET_DIR/records.jsonl"

folio() {
  "$UV" run --frozen folio "$@"
}

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" != "$actual" ]; then
    echo "smoke-cli: $label expected $expected, got $actual" >&2
    exit 1
  fi
}

# 1. validate empty sheet
folio validate "$SHEET_DIR" >/dev/null
assert_eq "empty count" "0" "$(folio count "$SHEET_DIR")"

# 2. upsert one record from stdin
echo '{"id": "a", "title": "Alpha", "count": 1}' | folio upsert "$SHEET_DIR" --file - --actor "human:smoke" >/dev/null
echo '{"id": "b", "title": "Beta", "count": 2}'  | folio upsert "$SHEET_DIR" --file - --actor "human:smoke" >/dev/null

assert_eq "after upsert count" "2" "$(folio count "$SHEET_DIR")"
assert_eq "filtered count" "1"   "$(folio count "$SHEET_DIR" --filter "count > 1")"

# 3. query returns ordered ids
QUERY_JSON="$(folio query "$SHEET_DIR" "SELECT id FROM records ORDER BY id")"
EXPECTED_QUERY='[{"id": "a"}, {"id": "b"}]'
assert_eq "query rows" "$EXPECTED_QUERY" "$QUERY_JSON"

# 4. list pagination cursor
LIST_PAGE_1="$(folio list "$SHEET_DIR" --limit 1 --fields id)"
case "$LIST_PAGE_1" in
  *'"next_cursor": "1"'*) ;;
  *) echo "smoke-cli: list page 1 missing cursor; got: $LIST_PAGE_1" >&2; exit 1 ;;
esac

LIST_PAGE_2="$(folio list "$SHEET_DIR" --limit 1 --fields id --cursor 1)"
case "$LIST_PAGE_2" in
  *'"next_cursor": null'*) ;;
  *) echo "smoke-cli: list page 2 should have null cursor; got: $LIST_PAGE_2" >&2; exit 1 ;;
esac

# 5. update an existing record
echo '{"id": "a", "count": 99}' | folio upsert "$SHEET_DIR" --file - --actor "agent:smoke" >/dev/null
UPDATED_JSON="$(folio query "$SHEET_DIR" "SELECT count FROM records WHERE id = 'a'")"
assert_eq "after update" '[{"count": 99}]' "$UPDATED_JSON"

# 6. delete by comma list
folio delete "$SHEET_DIR" --ids "a,b" --actor "human:smoke" >/dev/null
assert_eq "after delete count" "0" "$(folio count "$SHEET_DIR")"

# 7. write rejection through query
if folio query "$SHEET_DIR" "DELETE FROM records" >/dev/null 2>&1; then
  echo "smoke-cli: query should reject DELETE" >&2
  exit 1
fi

echo "smoke-cli: ok"
