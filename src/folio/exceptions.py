"""Folio exception hierarchy."""

from __future__ import annotations


class FolioError(Exception):
    """Base exception for all Folio errors."""


class ContractError(FolioError):
    """Raised when a sheet's ``contract.yaml`` cannot be loaded or validated."""
