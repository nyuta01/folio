"""Folio Viewer — local-only FastAPI + React UI.

Phase 5 V0..V3 surface. The backend imports the SDK directly (per
§19.1) and serves an optional pre-built React frontend from
``static_dir``. CSRF tokens are required on every mutating verb.
"""

from ._events import EventBus, make_event
from .server import ViewerSettings, build_app

__all__ = ["EventBus", "ViewerSettings", "build_app", "make_event"]
