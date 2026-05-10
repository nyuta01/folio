"""Phase 4 extension derivation kinds.

Each kind ships as a Pydantic v2 model and an executor function. The
discriminated union in ``folio.derivation`` carries the type tag; the
materialize loop in ``folio.sheet`` dispatches via ``isinstance`` so
each kind keeps its own validation rules and execution semantics
without growing the standard ``ai`` / ``import`` surface.
"""

from ._http import (
    HTTPDerivation,
    HTTPResponse,
    HTTPTransport,
    HTTPXTransport,
    StubHTTPTransport,
    execute_http,
)
from ._sql import SQLDerivation, execute_sql

__all__ = [
    "HTTPDerivation",
    "HTTPResponse",
    "HTTPTransport",
    "HTTPXTransport",
    "SQLDerivation",
    "StubHTTPTransport",
    "execute_http",
    "execute_sql",
]
