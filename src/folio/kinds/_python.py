"""``python`` extension kind.

Calls a script under ``<sheet>/scripts/`` (Phase 2) with the inputs
dict passed as a JSON-encoded argument. The script writes its result
(text or JSON) to stdout. Subprocess isolation, runtime cache
placement (ADR-0008), and the safe-name regex from
:mod:`folio.scripts` apply transparently.
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, model_validator
from typing_extensions import Self

from ..derivation import _BaseDerivation
from ..exceptions import FolioError
from ..scripts import run_script


class PythonDerivation(_BaseDerivation):
    """A derivation whose value comes from a script under ``scripts/``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["python"]
    script: str
    output: Literal["text", "json"] = "text"
    output_schema: dict[str, str] | None = None

    @model_validator(mode="after")
    def _validate_python_invariants(self) -> Self:
        if len(self.targets) >= 2:
            if self.output != "json":
                raise ValueError(
                    "multi-target python derivation must use output='json'"
                )
            if not self.output_schema:
                raise ValueError(
                    "multi-target python derivation must declare output_schema"
                )
            if set(self.output_schema.keys()) != set(self.targets):
                raise ValueError(
                    "python output_schema keys must equal targets: "
                    f"{sorted(self.output_schema.keys())} vs {sorted(self.targets)}"
                )
        elif self.output_schema is not None:
            raise ValueError(
                "single-target python derivation must not declare output_schema"
            )
        return self


def execute_python(
    derivation: PythonDerivation,
    inputs: dict[str, Any],
    *,
    sheet_path: Path,
    sheet_id: str,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    """Run the script and return ``{target: value, ...}``."""
    payload = _json.dumps(inputs, ensure_ascii=False, sort_keys=True)
    result = run_script(
        sheet_path=sheet_path,
        sheet_id=sheet_id,
        name=derivation.script,
        args=[payload],
        timeout_seconds=timeout_seconds,
    )
    if result.exit_code != 0:
        raise FolioError(
            f"python derivation script {derivation.script!r} exited with "
            f"{result.exit_code}: {(result.stderr or result.stdout).strip()}"
        )

    text = result.stdout.strip()

    if derivation.output == "text":
        return {derivation.targets[0]: text}

    try:
        data = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise FolioError(
            f"python derivation script returned invalid JSON: {exc.msg}"
        ) from exc

    if len(derivation.targets) == 1:
        return {derivation.targets[0]: data}

    if not isinstance(data, dict):
        raise FolioError(
            "multi-target python derivation expects a JSON object response, "
            f"got {type(data).__name__}"
        )

    missing = [target for target in derivation.targets if target not in data]
    if missing:
        raise FolioError(
            f"python derivation response missing targets: {sorted(missing)}"
        )
    return {target: data[target] for target in derivation.targets}


__all__ = ["PythonDerivation", "execute_python"]
