"""DuckDB query helper for Folio sheets.

A short-lived in-memory DuckDB connection is created per query so the SDK
remains stateless and reads always see the latest ``records.jsonl`` content.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

import duckdb

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

    Implementations enforce read-only behavior either by parsing the leading
    keyword of the SQL string or by connecting DuckDB in read-only mode
    (§10.3 of the design overview).
    """
    cleaned = _BLOCK_COMMENT_RE.sub(" ", _LINE_COMMENT_RE.sub("", sql))
    cleaned = cleaned.strip().lstrip("(").lstrip()
    if not cleaned:
        raise QueryError("query is empty")
    leading = cleaned.split(None, 1)[0].upper()
    if leading in _FORBIDDEN_LEADING_KEYWORDS:
        raise QueryError(
            f"only SELECT/WITH queries are allowed; got {leading!r}. "
            "Use upsert_records or delete_records for writes."
        )
    if leading not in {"SELECT", "WITH", "TABLE", "VALUES", "FROM", "DESCRIBE", "EXPLAIN", "SHOW"}:
        raise QueryError(f"unrecognized leading keyword {leading!r}")


def execute_query(
    contract: Contract,
    records_path: Path,
    sql: str,
    params: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute ``sql`` against the sheet's ``records`` view and return rows.

    DuckDB returns ``JSON``-typed columns as JSON-encoded strings, which is
    surprising for callers expecting the array/object value declared on the
    contract. Walk the result and ``json.loads`` any column whose contract
    ``logicalType`` is ``array`` or ``object``, leaving columns that aren't
    on the contract (aggregates, expression-only SELECTs) untouched.
    """
    ensure_select_only(sql)
    connection = duckdb.connect(":memory:")
    try:
        _create_records_view(connection, contract, records_path)
        cursor = connection.execute(sql, list(params) if params else [])
        column_names = [desc[0] for desc in cursor.description] if cursor.description else []
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


def _create_records_view(
    connection: "duckdb.DuckDBPyConnection",
    contract: Contract,
    records_path: Path,
) -> None:
    schema = contract.main_schema
    column_types = {prop.name: _DUCKDB_TYPE_BY_LOGICAL[prop.logical_type] for prop in schema.properties}

    if not records_path.exists() or records_path.stat().st_size == 0:
        empty_columns = ", ".join(
            f"NULL::{column_types[prop.name]} AS {_quote_ident(prop.name)}"
            for prop in schema.properties
        )
        connection.execute(
            f"CREATE OR REPLACE TEMP VIEW records AS SELECT {empty_columns} WHERE 1=0"
        )
        return

    columns_literal = "{" + ", ".join(
        f"'{_escape_string(name)}': '{_escape_string(type_)}'"
        for name, type_ in column_types.items()
    ) + "}"
    escaped_path = _escape_string(str(records_path))
    connection.execute(
        f"CREATE OR REPLACE TEMP VIEW records AS SELECT * FROM read_json("
        f"'{escaped_path}', format='newline_delimited', columns={columns_literal})"
    )


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _escape_string(value: str) -> str:
    return value.replace("'", "''")
