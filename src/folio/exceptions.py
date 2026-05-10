"""Folio exception hierarchy."""

from __future__ import annotations


class FolioError(Exception):
    """Base exception for all Folio errors."""


class ContractError(FolioError):
    """Raised when a sheet's ``contract.yaml`` cannot be loaded or validated."""


class SheetError(FolioError):
    """Raised when a sheet directory cannot be opened or is malformed."""


class RecordsError(FolioError):
    """Raised when ``records.jsonl`` cannot be parsed."""


class QueryError(FolioError):
    """Raised when a query is rejected or fails to execute."""


class OperationError(FolioError):
    """Raised when a write operation cannot complete (missing actor, primary key, etc.)."""


class PermissionDeniedError(OperationError):
    """Raised when an actor is not allowed to edit a field per ``x-editable-by``."""


class LockTimeoutError(FolioError):
    """Raised when the ``.lock`` file cannot be acquired within the timeout."""
