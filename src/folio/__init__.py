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
from .derivation import (
    AIDerivation,
    Derivation,
    DerivationError,
    ImportDerivation,
    MaterializationConfig,
    detect_cycles,
    load_derivation,
    load_derivations,
    topological_sort,
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
from .scripts import ScriptError, ScriptResult, discover_scripts
from .sheet import Sheet, open_sheet

__all__ = [
    "AIDerivation",
    "Contract",
    "ContractError",
    "Derivation",
    "DerivationError",
    "FolioError",
    "ImportDerivation",
    "LockTimeoutError",
    "LogicalType",
    "MaterializationConfig",
    "OperationError",
    "PermissionDeniedError",
    "Property",
    "QueryError",
    "RecordsError",
    "Schema",
    "ScriptError",
    "ScriptResult",
    "Sheet",
    "SheetError",
    "detect_cycles",
    "discover_scripts",
    "load_contract",
    "load_derivation",
    "load_derivations",
    "open_sheet",
    "topological_sort",
]

__version__ = "0.1.0"
