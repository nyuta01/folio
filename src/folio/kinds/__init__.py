"""Phase 4 extension derivation kinds.

Each kind ships as a Pydantic v2 model and an executor function. The
discriminated union in ``folio.derivation`` carries the type tag; the
materialize loop in ``folio.sheet`` dispatches via ``isinstance`` so
each kind keeps its own validation rules and execution semantics
without growing the standard ``ai`` / ``import`` surface.
"""

from ._cross_sheet import (
    CrossSheetDerivation,
    execute_cross_sheet,
    foreign_records_hash,
    resolve_foreign_sheet,
)
from ._http import (
    HTTPDerivation,
    HTTPResponse,
    HTTPTransport,
    HTTPXTransport,
    StubHTTPTransport,
    execute_http,
)
from ._python import PythonDerivation, execute_python
from ._sql import SQLDerivation, execute_sql

__all__ = [
    "CrossSheetDerivation",
    "HTTPDerivation",
    "HTTPResponse",
    "HTTPTransport",
    "HTTPXTransport",
    "PythonDerivation",
    "SQLDerivation",
    "StubHTTPTransport",
    "execute_cross_sheet",
    "execute_http",
    "execute_python",
    "execute_sql",
    "foreign_records_hash",
    "resolve_foreign_sheet",
]
