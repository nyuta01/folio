"""``folio-mcp`` console entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .server import build_server

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Folio MCP server (Anthropic-style Model Context Protocol).",
)


@app.command(help="Serve sheets under <root> over MCP.")
def serve(
    root: Path = typer.Option(
        ...,
        "--root",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Directory containing one or more Folio sheets.",
    ),
    actor: Optional[str] = typer.Option(
        None,
        "--actor",
        help="Default actor for write tools when callers do not pass one.",
    ),
    transport: str = typer.Option(
        "stdio",
        "--transport",
        help="MCP transport: stdio (default) or http.",
    ),
    bind: str = typer.Option(
        "127.0.0.1",
        "--bind",
        help="Bind address when --transport=http (local-only by default).",
    ),
    port: int = typer.Option(
        3001,
        "--port",
        min=1,
        max=65535,
        help="TCP port when --transport=http.",
    ),
) -> None:
    server = build_server(root=root, default_actor=actor)
    if transport == "stdio":
        server.run(transport="stdio")
    elif transport == "http":
        server.run(transport="http", host=bind, port=port)
    else:
        raise typer.BadParameter(
            f"unsupported transport {transport!r}; use 'stdio' or 'http'"
        )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
