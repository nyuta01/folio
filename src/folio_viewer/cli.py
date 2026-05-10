"""``folio-viewer`` console entry point.

Bind defaults to ``127.0.0.1`` per §19.1; override with ``--host`` only
when running inside a trusted environment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import uvicorn

from .server import build_app

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Folio Viewer (FastAPI + React, local-only).",
)


@app.command(help="Serve a Folio sheet on a local-only HTTP port.")
def serve(
    sheet: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Path to a Folio sheet directory.",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Bind address (defaults to 127.0.0.1; do not change without a reason).",
    ),
    port: int = typer.Option(
        3000,
        "--port",
        min=1,
        max=65535,
        help="TCP port to bind.",
    ),
    actor: Optional[str] = typer.Option(
        None,
        "--actor",
        help="Default actor for write routes when callers do not pass one.",
    ),
    static_dir: Optional[Path] = typer.Option(
        None,
        "--static-dir",
        exists=False,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Optional pre-built frontend directory (defaults to <repo>/viewer/dist if present).",
    ),
) -> None:
    resolved_static = static_dir
    if resolved_static is None:
        candidate = Path.cwd() / "viewer" / "dist"
        if candidate.is_dir():
            resolved_static = candidate
    fastapi_app = build_app(
        sheet_path=sheet,
        default_actor=actor,
        static_dir=resolved_static,
    )
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
