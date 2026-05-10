"""Folio Phase 0 ``Sheet`` operations.

Implements the six core operations from §10.2 of the design overview that
are part of Phase 0: ``get_contract``, ``query``, ``list_records``,
``get_record``, ``upsert_records``, ``delete_records``.

Phase 0 explicitly excludes ``materialize``, ``materialization_status``,
``provenance``, TOON output, and derivation execution.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import _query, _records
from ._lock import acquire_sheet_lock
from .contract import Contract, Property, Schema, load_contract
from .exceptions import (
    OperationError,
    PermissionDeniedError,
    SheetError,
)

DEFAULT_LIST_LIMIT = 50


@dataclass
class Sheet:
    """A handle to a Folio sheet directory."""

    path: Path
    actor: str | None = None
    _contract: Contract = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if not self.path.is_dir():
            raise SheetError(f"sheet path is not a directory: {self.path}")
        self._contract = load_contract(self.path)

    # --- properties -----------------------------------------------------

    @property
    def contract(self) -> Contract:
        return self._contract

    @property
    def records_path(self) -> Path:
        return self.path / "records.jsonl"

    @property
    def main_schema(self) -> Schema:
        return self._contract.main_schema

    # --- operation: get_contract ----------------------------------------

    def get_contract(self) -> Contract:
        """Return the loaded contract."""
        return self._contract

    # --- operation: query -----------------------------------------------

    def query(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a SELECT-only DuckDB query against the ``records`` view."""
        return _query.execute_query(self._contract, self.records_path, sql, params)

    # --- operation: list_records ----------------------------------------

    def list_records(
        self,
        filter: str | None = None,  # noqa: A002 — keeps spec naming
        fields: Sequence[str] | None = None,
        limit: int = DEFAULT_LIST_LIMIT,
        cursor: str | None = None,
        params: Sequence[Any] | None = None,
    ) -> dict[str, Any]:
        """List records.

        Returns a dict with ``records``, ``format``, ``limit``, and
        ``next_cursor``. ``format`` is always ``"json"`` in Phase 0.
        """
        if limit <= 0:
            raise OperationError("limit must be positive")

        offset = int(cursor) if cursor else 0
        if fields is not None:
            self._validate_field_names(fields)
            select_clause = ", ".join(_quote_ident(name) for name in fields)
        else:
            select_clause = "*"

        sql_parts = [f"SELECT {select_clause} FROM records"]
        if filter:
            sql_parts.append(f"WHERE {filter}")
        sql_parts.append(f"LIMIT {limit + 1}")
        if offset:
            sql_parts.append(f"OFFSET {offset}")
        sql = " ".join(sql_parts)

        rows = self.query(sql, params)
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = str(offset + limit) if has_more else None
        return {
            "records": rows,
            "format": "json",
            "limit": limit,
            "next_cursor": next_cursor,
        }

    # --- operation: get_record ------------------------------------------

    def get_record(
        self,
        id: str,  # noqa: A002 — keeps spec naming
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single record by primary key, or ``None`` if missing."""
        primary_key = self._primary_key_name()
        result = self.list_records(
            filter=f"{_quote_ident(primary_key)} = ?",
            params=[id],
            fields=fields,
            limit=2,
        )
        records = result["records"]
        if not records:
            return None
        return records[0]

    # --- operation: upsert_records --------------------------------------

    def upsert_records(
        self,
        records: Iterable[dict[str, Any]],
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Insert or update records by primary key. Requires ``actor``."""
        effective_actor = self._require_actor(actor, "upsert_records")
        prepared = list(records)
        primary_key = self._primary_key_name()

        for record in prepared:
            if not isinstance(record, dict):
                raise OperationError("each record must be a dict")
            if primary_key not in record:
                raise OperationError(
                    f"record missing primaryKey field {primary_key!r}: {record!r}"
                )
            self._check_editable_by(record, effective_actor)

        with acquire_sheet_lock(self.path):
            existing = _records.read_records(self.records_path)
            index_by_pk: dict[Any, int] = {}
            for position, row in enumerate(existing):
                if primary_key in row:
                    index_by_pk[row[primary_key]] = position

            inserted = 0
            updated = 0
            for record in prepared:
                pk_value = record[primary_key]
                if pk_value in index_by_pk:
                    merged = {**existing[index_by_pk[pk_value]], **record}
                    self._validate_required_fields(merged)
                    existing[index_by_pk[pk_value]] = merged
                    updated += 1
                else:
                    self._validate_required_fields(record)
                    existing.append(record)
                    index_by_pk[pk_value] = len(existing) - 1
                    inserted += 1

            _records.atomic_write_records(self.records_path, existing)

        return {
            "inserted": inserted,
            "updated": updated,
            "total": len(existing),
        }

    # --- operation: delete_records --------------------------------------

    def delete_records(
        self,
        ids: Iterable[str],
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Delete records whose primary key is in ``ids``. Requires ``actor``."""
        self._require_actor(actor, "delete_records")
        primary_key = self._primary_key_name()
        target_ids = set(ids)

        with acquire_sheet_lock(self.path):
            existing = _records.read_records(self.records_path)
            kept = [row for row in existing if row.get(primary_key) not in target_ids]
            deleted = len(existing) - len(kept)
            _records.atomic_write_records(self.records_path, kept)

        return {
            "deleted": deleted,
            "remaining": len(kept),
        }

    # --- internal helpers -----------------------------------------------

    def _primary_key_name(self) -> str:
        for prop in self.main_schema.properties:
            if prop.primary_key:
                return prop.name
        raise OperationError(
            f"contract for sheet {self.path} declares no primaryKey field"
        )

    def _require_actor(self, actor: str | None, operation: str) -> str:
        effective = actor if actor is not None else self.actor
        if not effective:
            raise OperationError(f"{operation} requires an actor")
        return effective

    def _validate_field_names(self, fields: Sequence[str]) -> None:
        valid_names = {prop.name for prop in self.main_schema.properties}
        unknown = [name for name in fields if name not in valid_names]
        if unknown:
            raise OperationError(f"unknown field(s) in projection: {unknown}")

    def _validate_required_fields(self, record: dict[str, Any]) -> None:
        for prop in self.main_schema.properties:
            if not prop.required or prop.derived:
                continue
            if record.get(prop.name) is None:
                raise OperationError(
                    f"required field {prop.name!r} is missing or null"
                )

    def _check_editable_by(self, record: dict[str, Any], actor: str) -> None:
        for prop in self.main_schema.properties:
            if prop.name not in record:
                continue
            if prop.editable_by is None:
                continue
            if not _actor_matches_any(actor, prop.editable_by):
                raise PermissionDeniedError(
                    f"actor {actor!r} cannot edit field {prop.name!r}; "
                    f"allowed: {prop.editable_by}"
                )


def open_sheet(path: str | Path, actor: str | None = None) -> Sheet:
    """Open a sheet directory and return a :class:`Sheet` handle."""
    return Sheet(path=Path(path), actor=actor)


# ---------------------------------------------------------------------------
# Local helpers (kept here to avoid leaking through the public ``__init__``)
# ---------------------------------------------------------------------------


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _actor_matches_any(actor: str, patterns: Sequence[str]) -> bool:
    return any(_actor_matches(actor, pattern) for pattern in patterns)


def _actor_matches(actor: str, pattern: str) -> bool:
    if pattern == actor:
        return True
    if pattern == "*":
        return True
    return fnmatch.fnmatchcase(actor, pattern)


__all__ = ["Sheet", "open_sheet"]
