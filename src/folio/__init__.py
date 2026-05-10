"""Folio: portable, AI-native data sheets.

This is the Phase 0 surface: contract.yaml loading and validation.
See docs/design-docs/overview.md for the full specification.
"""

from .contract import (
    Contract,
    LogicalType,
    Property,
    Schema,
    load_contract,
)
from .exceptions import ContractError, FolioError

__all__ = [
    "Contract",
    "ContractError",
    "FolioError",
    "LogicalType",
    "Property",
    "Schema",
    "load_contract",
]

__version__ = "0.1.0"
