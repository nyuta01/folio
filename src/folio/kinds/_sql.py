"""``sql`` extension kind.

Evaluates a DuckDB SELECT expression against the same ``records`` view
used by ``Sheet.query``. Inputs are passed as ``?`` parameters in the
order declared by ``inputs:``. Single-target derivations take the first
column of the first row; multi-target derivations require an
``output_schema`` whose keys list the columns to project.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, model_validator
from typing_extensions import Self

from .._query import ensure_select_only, execute_query
from ..contract import Contract
from ..derivation import _BaseDerivation
from ..exceptions import FolioError


class SQLDerivation(_BaseDerivation):
    """A derivation whose value comes from a DuckDB SELECT expression."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["sql"]
    expression: str
    output_schema: dict[str, str] | None = None

    @model_validator(mode="after")
    def _validate_sql_invariants(self) -> Self:
        try:
            ensure_select_only(self.expression)
        except FolioError as exc:
            # Re-raise as ValueError so Pydantic wraps it in ValidationError,
            # which load_derivation converts into DerivationError.
            raise ValueError(str(exc)) from exc
        if len(self.targets) >= 2:
            if not self.output_schema:
                raise ValueError(
                    "multi-target sql derivation must declare output_schema"
                )
            if set(self.output_schema.keys()) != set(self.targets):
                raise ValueError(
                    "sql output_schema keys must equal targets: "
                    f"{sorted(self.output_schema.keys())} vs {sorted(self.targets)}"
                )
        elif self.output_schema is not None:
            raise ValueError(
                "single-target sql derivation must not declare output_schema"
            )
        return self


def execute_sql(
    derivation: SQLDerivation,
    inputs: dict[str, Any],
    *,
    contract: Contract,
    records_path: Path,
) -> dict[str, Any]:
    """Run the derivation's SQL expression and project the result onto targets."""
    params = [inputs.get(field) for field in derivation.inputs]
    rows = execute_query(contract, records_path, derivation.expression, params)
    if not rows:
        if len(derivation.targets) == 1:
            return {derivation.targets[0]: None}
        return {target: None for target in derivation.targets}

    first = rows[0]
    if len(derivation.targets) == 1:
        if not first:
            raise FolioError(
                "sql derivation returned an empty row; expected at least one column"
            )
        first_value = next(iter(first.values()))
        return {derivation.targets[0]: first_value}

    missing = [target for target in derivation.targets if target not in first]
    if missing:
        raise FolioError(
            f"sql derivation result missing target columns: {sorted(missing)}"
        )
    return {target: first[target] for target in derivation.targets}


__all__ = ["SQLDerivation", "execute_sql"]
