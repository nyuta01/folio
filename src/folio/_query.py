"""DuckDB query helper for Folio sheets.

A short-lived in-memory DuckDB connection is created per query so the SDK
remains stateless and reads always see the latest ``records.jsonl`` content.
Records are loaded through Python and inserted into a temporary DuckDB table;
DuckDB external file access stays disabled for caller-supplied SQL.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

import duckdb

from . import _records
from .contract import Contract, LogicalType
from .exceptions import QueryError

_DUCKDB_TYPE_BY_LOGICAL: dict[LogicalType, str] = {
    "string": "VARCHAR",
    "integer": "BIGINT",
    "number": "DOUBLE",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
    "array": "JSON",
    "object": "JSON",
}

_FORBIDDEN_LEADING_KEYWORDS = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "CREATE",
        "DROP",
        "ALTER",
        "REPLACE",
        "TRUNCATE",
        "COPY",
        "MERGE",
        "ATTACH",
        "DETACH",
        "INSTALL",
        "LOAD",
        "PRAGMA",
        "CALL",
        "GRANT",
        "REVOKE",
    }
)

_LINE_COMMENT_RE = re.compile(r"--.*?$", re.MULTILINE)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def ensure_select_only(sql: str) -> None:
    """Reject statements that are not pure ``SELECT``/``WITH`` queries.

    This check blocks DuckDB writes and stacked statements; the
    connection-level external-access setting below separately blocks
    file-reading SELECTs (§10.3 of the design overview).
    """
    cleaned = _BLOCK_COMMENT_RE.sub(" ", _LINE_COMMENT_RE.sub("", sql))
    cleaned = cleaned.strip().lstrip("(").lstrip()
    if not cleaned:
        raise QueryError("query is empty")
    _ensure_single_statement(cleaned)
    leading = cleaned.split(None, 1)[0].upper()
    if leading in _FORBIDDEN_LEADING_KEYWORDS:
        raise QueryError(
            f"only SELECT/WITH queries are allowed; got {leading!r}. "
            "Use upsert_records or delete_records for writes."
        )
    if leading not in {
        "SELECT",
        "WITH",
        "TABLE",
        "VALUES",
        "FROM",
        "DESCRIBE",
        "EXPLAIN",
        "SHOW",
    }:
        raise QueryError(f"unrecognized leading keyword {leading!r}")


def _ensure_single_statement(sql: str) -> None:
    """Reject stacked SQL statements while allowing one trailing semicolon."""
    in_single_quote = False
    in_double_quote = False
    index = 0
    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""
        if in_single_quote:
            if char == "'" and next_char == "'":
                index += 2
                continue
            if char == "'":
                in_single_quote = False
        elif in_double_quote:
            if char == '"' and next_char == '"':
                index += 2
                continue
            if char == '"':
                in_double_quote = False
        elif char == "'":
            in_single_quote = True
        elif char == '"':
            in_double_quote = True
        elif char == ";" and sql[index + 1 :].strip():
            raise QueryError("only one SQL statement is allowed")
        index += 1


def execute_query(
    contract: Contract,
    records_path: Path,
    sql: str,
    params: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute ``sql`` against the sheet's ``records`` relation and return rows.

    DuckDB returns ``JSON``-typed columns as JSON-encoded strings, which is
    surprising for callers expecting the array/object value declared on the
    contract. Walk the result and ``json.loads`` any column whose contract
    ``logicalType`` is ``array`` or ``object``, leaving columns that aren't
    on the contract (aggregates, expression-only SELECTs) untouched.
    """
    ensure_select_only(sql)
    connection = duckdb.connect(
        ":memory:", config={"enable_external_access": False}
    )
    try:
        _create_records_table(connection, contract, records_path)
        cursor = connection.execute(sql, list(params) if params else [])
        column_names = (
            [desc[0] for desc in cursor.description] if cursor.description else []
        )
        rows = cursor.fetchall()
    except duckdb.Error as exc:
        raise QueryError(f"query failed: {exc}") from exc
    finally:
        connection.close()

    json_columns = {
        prop.name
        for prop in contract.main_schema.properties
        if prop.logical_type in ("array", "object") and prop.name in column_names
    }

    results: list[dict[str, Any]] = []
    for row in rows:
        record = dict(zip(column_names, row))
        for name in json_columns:
            raw = record.get(name)
            if isinstance(raw, str):
                try:
                    record[name] = json.loads(raw)
                except json.JSONDecodeError:
                    # Leave the raw string in place; callers can decide
                    # whether a malformed JSON cell is recoverable.
                    pass
        results.append(record)
    return results


def _create_records_table(
    connection: "duckdb.DuckDBPyConnection",
    contract: Contract,
    records_path: Path,
) -> None:
    schema = contract.main_schema
    column_types = {
        prop.name: _DUCKDB_TYPE_BY_LOGICAL[prop.logical_type]
        for prop in schema.properties
    }

    columns_sql = ", ".join(
        f"{_quote_ident(prop.name)} {column_types[prop.name]}"
        for prop in schema.properties
    )
    connection.execute(f"CREATE TEMP TABLE records ({columns_sql})")

    records = _records.read_records(records_path)
    if not records:
        return

    placeholders = ", ".join("?" for _ in schema.properties)
    insert_sql = f"INSERT INTO records VALUES ({placeholders})"
    rows = [
        [
            _coerce_record_value(record.get(prop.name), prop.logical_type)
            for prop in schema.properties
        ]
        for record in records
    ]
    connection.executemany(insert_sql, rows)


def _coerce_record_value(value: Any, logical_type: LogicalType) -> Any:
    if logical_type in ("array", "object") and value is not None:
        return json.dumps(value, ensure_ascii=False)
    return value


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'
