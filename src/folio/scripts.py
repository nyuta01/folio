"""Phase 2 reusable-script discovery and execution.

The script runtime cache lives outside the sheet at
``<user-cache>/folio/<sheet-id>/runtime/`` per ADR-0008 so a ``tar`` of a
sheet stays portable. Scripts receive the sheet path as their first
argument so they can resolve ``records.jsonl`` / ``contract.yaml``
without extra setup.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import platformdirs

from .exceptions import FolioError


class ScriptError(FolioError):
    """Raised when a script cannot be discovered or executed."""


SCRIPT_LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".sh": "shell",
}


_SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


@dataclass
class ScriptResult:
    """The outcome of one script invocation."""

    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


# --- discovery -------------------------------------------------------------


def discover_scripts(sheet_path: str | Path) -> dict[str, Path]:
    """Return ``{basename: path}`` for runnable scripts under ``sheet/scripts/``.

    Subdirectories and unsupported extensions are ignored. Two scripts that
    share the same basename (e.g., ``hello.py`` and ``hello.sh``) raise
    :class:`ScriptError` since the runner cannot tell them apart.
    """
    scripts_dir = Path(sheet_path) / "scripts"
    if not scripts_dir.is_dir():
        return {}

    found: dict[str, Path] = {}
    for entry in sorted(scripts_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix not in SCRIPT_LANGUAGE_BY_EXTENSION:
            continue
        name = entry.stem
        if name in found:
            raise ScriptError(
                f"duplicate script basename {name!r}: "
                f"{found[name].name} vs {entry.name}"
            )
        found[name] = entry
    return found


# --- runtime placement -----------------------------------------------------


def runtime_root_for_sheet(sheet_id: str) -> Path:
    """Resolve ``<user-cache>/folio/<sheet-id>/runtime/`` (ADR-0008)."""
    return Path(platformdirs.user_cache_dir("folio")) / sheet_id / "runtime"


# --- execution -------------------------------------------------------------


def run_script(
    sheet_path: str | Path,
    sheet_id: str,
    name: str,
    args: Sequence[str] | None = None,
    timeout_seconds: float = 60.0,
) -> ScriptResult:
    """Execute ``scripts/<name>.<ext>`` with the sheet path as ``argv[1]``."""
    if not _SAFE_NAME_PATTERN.fullmatch(name):
        raise ScriptError(
            f"script name must match {_SAFE_NAME_PATTERN.pattern}; got {name!r}"
        )

    sheet_path = Path(sheet_path)
    discovered = discover_scripts(sheet_path)
    if name not in discovered:
        raise ScriptError(
            f"script {name!r} not found under {sheet_path / 'scripts'}"
        )

    script_path = discovered[name]
    language = SCRIPT_LANGUAGE_BY_EXTENSION[script_path.suffix]
    invocation: list[str]
    if language == "python":
        invocation = [
            str(_resolve_python(sheet_path, sheet_id)),
            str(script_path),
            str(sheet_path),
            *(args or []),
        ]
    elif language == "shell":
        bash = shutil.which("bash") or "/bin/bash"
        invocation = [
            bash,
            str(script_path),
            str(sheet_path),
            *(args or []),
        ]
    else:  # pragma: no cover - guarded by SCRIPT_LANGUAGE_BY_EXTENSION
        raise ScriptError(f"unsupported language for {script_path.name}: {language}")

    return _run(invocation, sheet_path, timeout_seconds)


def _resolve_python(sheet_path: Path, sheet_id: str) -> Path:
    """Pick the Python interpreter for a sheet's scripts.

    Without ``scripts/requirements.txt`` the runner uses the project
    interpreter (``sys.executable``). When requirements are present, a
    venv is materialized at
    ``<runtime>/python/.venv/`` on first use.
    """
    requirements = sheet_path / "scripts" / "requirements.txt"
    if not requirements.is_file():
        return Path(sys.executable)

    runtime = runtime_root_for_sheet(sheet_id) / "python"
    runtime.mkdir(parents=True, exist_ok=True)
    venv_dir = runtime / ".venv"
    if not venv_dir.is_dir():
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    str(venv_dir / "bin" / "pip"),
                    "install",
                    "--quiet",
                    "--disable-pip-version-check",
                    "-r",
                    str(requirements),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr or exc.stdout or ""
            raise ScriptError(
                f"failed to materialize script venv: {stderr.strip()}"
            ) from exc

    return venv_dir / "bin" / "python"


def _run(
    cmd: list[str],
    cwd: Path,
    timeout_seconds: float,
) -> ScriptResult:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ScriptError(
            f"script timed out after {timeout_seconds:.1f}s"
        ) from exc
    duration = time.monotonic() - start
    return ScriptResult(
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_seconds=duration,
    )


__all__ = [
    "SCRIPT_LANGUAGE_BY_EXTENSION",
    "ScriptError",
    "ScriptResult",
    "discover_scripts",
    "run_script",
    "runtime_root_for_sheet",
]
