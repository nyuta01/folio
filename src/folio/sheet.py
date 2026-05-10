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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import _ai_kind, _import_kind, _provenance, _query, _records, scripts as _scripts_mod
from ._cache import (
    compute_input_hash,
    default_cache_root,
    read_cache,
    sha256_file,
    write_cache,
)
from ._lock import acquire_sheet_lock
from .contract import Contract, Property, Schema, load_contract
from .derivation import (
    AIDerivation,
    Derivation,
    DerivationFile,
    ImportDerivation,
    load_derivation_files,
    topological_sort,
)
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

    # --- operation: materialize -----------------------------------------

    def materialize(
        self,
        targets: Sequence[str] | None = None,
        record_ids: Sequence[str] | None = None,
        force: bool = False,
        actor: str | None = None,
        ai_client: _ai_kind.AIClient | None = None,
    ) -> dict[str, Any]:
        """Execute derivations for the selected records and targets.

        Returns the §10.6 envelope: ``{materialized, skipped, failures,
        total_cost}``. Failures are reported per record × field rather
        than raised so a large materialize run remains reasonable.
        """
        effective_actor = self._require_actor(actor, "materialize")

        files = load_derivation_files(self.path)
        if not files:
            return {
                "materialized": 0,
                "skipped": 0,
                "failures": [],
                "total_cost": 0.0,
            }

        by_target: dict[str, Derivation] = {}
        file_for_target: dict[str, Path] = {}
        for df in files:
            for target in df.derivation.targets:
                by_target[target] = df.derivation
                file_for_target[target] = df.path

        if targets is None:
            selected = set(by_target.keys())
        else:
            selected = set(targets)
            unknown = selected - set(by_target.keys())
            if unknown:
                raise OperationError(
                    f"unknown derivation target(s): {sorted(unknown)}"
                )

        order = topological_sort(by_target)
        target_position = {target: index for index, target in enumerate(order)}
        ordered_files: list[DerivationFile] = []
        seen_files: set[int] = set()
        for target in order:
            if target not in selected:
                continue
            df = next(f for f in files if target in f.derivation.targets)
            if id(df) in seen_files:
                continue
            seen_files.add(id(df))
            ordered_files.append(df)

        cache_root = default_cache_root(self.contract.id)
        client = ai_client if ai_client is not None else _default_ai_client_factory()
        primary_key = self._primary_key_name()

        materialized = 0
        skipped = 0
        failures: list[dict[str, Any]] = []
        total_cost = 0.0
        pending_provenance: list[dict[str, Any]] = []

        with acquire_sheet_lock(self.path):
            records = _records.read_records(self.records_path)
            indices_by_id: dict[Any, int] = {}
            for position, row in enumerate(records):
                if primary_key in row:
                    indices_by_id[row[primary_key]] = position

            target_record_ids: list[Any]
            if record_ids is None:
                target_record_ids = list(indices_by_id.keys())
            else:
                target_record_ids = list(record_ids)

            for df in ordered_files:
                derivation = df.derivation
                derivation_file_hash = sha256_file(df.path)
                derivation_targets = [
                    target for target in derivation.targets if target in selected
                ]

                prompt_body: str | None = None
                source_rows: list[dict[str, Any]] | None = None
                source_file_hash: str | None = None
                if isinstance(derivation, AIDerivation):
                    prompt_body = _ai_kind.resolve_prompt_body(self.path, derivation)
                elif isinstance(derivation, ImportDerivation):
                    source_path = (self.path / derivation.source).resolve()
                    source_file_hash = sha256_file(source_path)
                    source_rows = _import_kind.load_import_source(
                        self.path, derivation.source
                    )

                for record_id in target_record_ids:
                    position = indices_by_id.get(record_id)
                    if position is None:
                        for target in derivation_targets:
                            failures.append(
                                {
                                    "record_id": record_id,
                                    "field": target,
                                    "error": f"record {record_id!r} not found",
                                    "error_type": "RecordNotFound",
                                }
                            )
                        continue

                    record = records[position]
                    inputs = {field_name: record.get(field_name) for field_name in derivation.inputs}

                    # Spec import inputs: [] would collapse every record to the
                    # same cache key. Augment with the primary-key value so the
                    # cache differentiates records without changing the
                    # ai-kind contract.
                    hash_inputs = dict(inputs)
                    if isinstance(derivation, ImportDerivation):
                        hash_inputs[primary_key] = record.get(primary_key)

                    try:
                        input_hash = compute_input_hash(
                            derivation,
                            derivation_file_hash=derivation_file_hash,
                            inputs=hash_inputs,
                            prompt_body=prompt_body,
                            source_file_hash=source_file_hash,
                        )
                    except Exception as exc:
                        for target in derivation_targets:
                            failures.append(
                                {
                                    "record_id": record_id,
                                    "field": target,
                                    "error": str(exc),
                                    "error_type": type(exc).__name__,
                                }
                            )
                        continue

                    # respect_human_override applies per target
                    blocked = False
                    if not force and derivation.materialization.respect_human_override:
                        for target in derivation_targets:
                            latest = _provenance.latest_provenance(
                                self.path, record_id, target
                            )
                            if latest is not None and latest.get("source") == "human_override":
                                skipped += 1
                                blocked = True
                        if blocked and len(derivation_targets) == 1:
                            continue
                        if blocked:
                            # Skip the whole derivation if any target is locked.
                            continue

                    if not force:
                        # Stale check: if every target is fresh, skip the whole derivation.
                        any_stale = False
                        for target in derivation_targets:
                            latest = _provenance.latest_provenance(
                                self.path, record_id, target
                            )
                            if _provenance.is_stale(latest, input_hash):
                                any_stale = True
                                break
                        if not any_stale:
                            skipped += len(derivation_targets)
                            continue

                    cached = read_cache(cache_root, input_hash)
                    cost_usd: float | None = None
                    try:
                        if cached is not None:
                            values = cached["values"]
                            cost_usd = cached.get("cost_usd")
                        elif isinstance(derivation, AIDerivation):
                            result = _ai_kind.materialize_ai(
                                derivation,
                                inputs,
                                client=client,
                                prompt_body=prompt_body,
                            )
                            values = result.values
                            cost_usd = result.cost_usd
                            write_cache(
                                cache_root,
                                input_hash,
                                {
                                    "values": result.values,
                                    "cost_usd": result.cost_usd,
                                    "input_tokens": result.input_tokens,
                                    "output_tokens": result.output_tokens,
                                },
                            )
                        elif isinstance(derivation, ImportDerivation):
                            assert source_rows is not None
                            values = _import_kind.apply_import(
                                derivation, source_rows, record.get(primary_key)
                            )
                            if not values:
                                skipped += len(derivation_targets)
                                continue
                            cost_usd = None
                            write_cache(
                                cache_root,
                                input_hash,
                                {"values": values, "cost_usd": None},
                            )
                        else:  # pragma: no cover - guarded by Pydantic discriminator
                            raise OperationError(
                                f"unsupported derivation kind: {type(derivation).__name__}"
                            )
                    except Exception as exc:
                        for target in derivation_targets:
                            failures.append(
                                {
                                    "record_id": record_id,
                                    "field": target,
                                    "error": str(exc),
                                    "error_type": type(exc).__name__,
                                }
                            )
                        continue

                    # Apply values for targets that are part of the selection.
                    timestamp = _utc_now_iso()
                    for target in derivation_targets:
                        if target in values:
                            records[position][target] = values[target]

                            entry: dict[str, Any] = {
                                "record_id": record_id,
                                "field": target,
                                "source": derivation.kind,
                                "actor": effective_actor,
                                "at": timestamp,
                                "input_hash": input_hash,
                            }
                            if isinstance(derivation, AIDerivation):
                                entry["model"] = derivation.model
                                if cost_usd is not None:
                                    entry["cost_usd"] = cost_usd
                                    total_cost += cost_usd
                            pending_provenance.append(entry)
                            materialized += 1

            _records.atomic_write_records(self.records_path, records)
            for entry in pending_provenance:
                _provenance.append_provenance(self.path, entry)

        return {
            "materialized": materialized,
            "skipped": skipped,
            "failures": failures,
            "total_cost": total_cost,
        }

    # --- operation: materialization_status ------------------------------

    def materialization_status(
        self,
        targets: Sequence[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Return per-target materialization counts and the latest entry."""
        files = load_derivation_files(self.path)
        by_target: dict[str, Derivation] = {}
        for df in files:
            for target in df.derivation.targets:
                by_target[target] = df.derivation

        if targets is None:
            selected = sorted(by_target.keys())
        else:
            unknown = [t for t in targets if t not in by_target]
            if unknown:
                raise OperationError(
                    f"unknown derivation target(s): {sorted(unknown)}"
                )
            selected = list(targets)

        primary_key = self._primary_key_name()
        records = _records.read_records(self.records_path)
        record_ids = [row[primary_key] for row in records if primary_key in row]
        provenance_entries = _provenance.read_provenance(self.path)

        result: dict[str, dict[str, Any]] = {}
        for target in selected:
            target_entries = [e for e in provenance_entries if e.get("field") == target]
            ai_count = sum(1 for e in target_entries if e.get("source") == "ai")
            import_count = sum(1 for e in target_entries if e.get("source") == "import")
            human_count = sum(
                1 for e in target_entries if e.get("source") == "human_override"
            )
            with_provenance = len({e.get("record_id") for e in target_entries})
            last_at = target_entries[-1].get("at") if target_entries else None
            last_actor = target_entries[-1].get("actor") if target_entries else None

            result[target] = {
                "total_records": len(record_ids),
                "with_provenance": with_provenance,
                "ai_count": ai_count,
                "import_count": import_count,
                "human_override_count": human_count,
                "last_at": last_at,
                "last_actor": last_actor,
            }
        return result

    # --- operation: run_script ------------------------------------------

    def run_script(
        self,
        name: str,
        args: Sequence[str] | None = None,
        timeout_seconds: float = 60.0,
    ) -> _scripts_mod.ScriptResult:
        """Execute ``scripts/<name>.<ext>`` with the sheet path as ``argv[1]``."""
        return _scripts_mod.run_script(
            self.path,
            self.contract.id,
            name=name,
            args=args,
            timeout_seconds=timeout_seconds,
        )

    # --- operation: provenance ------------------------------------------

    def provenance(
        self,
        record_id: str,
        field: str,  # noqa: A002 — keeps spec naming
        history: bool = False,
    ) -> Any:
        """Return the latest provenance entry, or the full history."""
        if history:
            return _provenance.field_history(self.path, record_id, field)
        return _provenance.latest_provenance(self.path, record_id, field)

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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_ai_client_factory() -> _ai_kind.AIClient:
    """Construct the default ``AIClient`` for production materialize calls.

    Tests and the offline materialize smoke replace this factory with a
    :class:`folio._ai_kind.StubAIClient`.
    """
    return _ai_kind.AnthropicClientAdapter()


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
