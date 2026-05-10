"""Folio: portable, AI-native data sheets.

Phase 0 surface: ``contract.yaml`` loading and validation, plus the six
core operations on a ``Sheet``. See ``docs/design-docs/overview.md`` for the
full specification.
"""

from .contract import (
    Contract,
    LogicalType,
    Property,
    Schema,
    load_contract,
)
from .exceptions import (
    ContractError,
    FolioError,
    LockTimeoutError,
    OperationError,
    PermissionDeniedError,
    QueryError,
    RecordsError,
    SheetError,
)
from .sheet import Sheet, open_sheet

__all__ = [
    "Contract",
    "ContractError",
    "FolioError",
    "LockTimeoutError",
    "LogicalType",
    "OperationError",
    "PermissionDeniedError",
    "Property",
    "QueryError",
    "RecordsError",
    "Schema",
    "Sheet",
    "SheetError",
    "load_contract",
    "open_sheet",
]

__version__ = "0.1.0"
