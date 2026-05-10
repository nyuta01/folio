"""Pydantic v2 models for ``derivations/<field>.yaml``.

The derivation format follows §8 of the design overview. Phase 1 supports
the standard kinds ``ai`` and ``import``; extension kinds (``sql``,
``http``, ``python``, ``cross_sheet``) are deferred to Phase 4.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, Union

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from typing_extensions import Self

from .exceptions import FolioError


class DerivationError(FolioError):
    """Raised when a ``derivations/<field>.yaml`` file is missing or invalid."""


# --- nested models ---------------------------------------------------------


class MaterializationConfig(BaseModel):
    """Per-derivation materialization controls."""

    model_config = ConfigDict(extra="forbid")

    trigger: Literal["on_demand"] = "on_demand"
    respect_human_override: bool = True


class _BaseDerivation(BaseModel):
    """Fields shared by every derivation kind."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    targets: list[str] = Field(min_length=1)
    inputs: list[str] = Field(default_factory=list)
    materialization: MaterializationConfig = Field(
        default_factory=MaterializationConfig
    )

    @model_validator(mode="after")
    def _validate_targets_unique(self) -> Self:
        if len(set(self.targets)) != len(self.targets):
            raise ValueError(f"targets must be unique: {self.targets}")
        return self


# --- ai kind ---------------------------------------------------------------


class AIDerivation(_BaseDerivation):
    """The ``ai`` kind. Drives the Anthropic SDK (Phase 1)."""

    kind: Literal["ai"]
    model: str
    prompt: str | None = None
    prompt_ref: str | None = None
    output: Literal["text", "json"]
    output_schema: dict[str, str] | None = None

    @model_validator(mode="after")
    def _validate_ai_invariants(self) -> Self:
        if (self.prompt is None) == (self.prompt_ref is None):
            raise ValueError(
                "ai derivation must specify exactly one of 'prompt' or 'prompt_ref'"
            )
        if len(self.targets) >= 2:
            if self.output != "json":
                raise ValueError(
                    "multi-target ai derivation must use output='json'"
                )
            if not self.output_schema:
                raise ValueError(
                    "multi-target ai derivation must declare output_schema"
                )
            if set(self.output_schema.keys()) != set(self.targets):
                raise ValueError(
                    "output_schema keys must equal targets: "
                    f"{sorted(self.output_schema.keys())} vs {sorted(self.targets)}"
                )
        else:
            if self.output_schema is not None:
                raise ValueError(
                    "single-target ai derivation must not declare output_schema "
                    "(driven by the field's logicalType)"
                )
        return self


# --- import kind -----------------------------------------------------------


class ImportDerivation(_BaseDerivation):
    """The ``import`` kind. Pulls values from a file inside the sheet."""

    kind: Literal["import"]
    source: str
    key_field: str
    value_field: str | None = None
    value_fields: dict[str, str] | None = None

    @model_validator(mode="after")
    def _validate_import_invariants(self) -> Self:
        single_value = self.value_field is not None
        multi_value = self.value_fields is not None
        if single_value and multi_value:
            raise ValueError(
                "import derivation must specify exactly one of "
                "'value_field' or 'value_fields'"
            )
        if not single_value and not multi_value:
            raise ValueError(
                "import derivation must specify either 'value_field' "
                "or 'value_fields'"
            )

        if len(self.targets) == 1:
            if multi_value and self.value_fields is not None and (
                set(self.value_fields.keys()) != set(self.targets)
            ):
                raise ValueError(
                    "single-target import 'value_fields' keys must equal targets"
                )
        else:
            if single_value:
                raise ValueError(
                    "multi-target import derivation must use 'value_fields'"
                )
            if (
                self.value_fields is None
                or set(self.value_fields.keys()) != set(self.targets)
            ):
                raise ValueError(
                    "multi-target import 'value_fields' keys must equal targets"
                )
        return self


# --- discriminated union ---------------------------------------------------


def _build_derivation_adapter() -> TypeAdapter[Any]:
    """Construct the discriminated TypeAdapter, including extension kinds.

    Imported lazily so ``folio.derivation`` does not depend on
    ``folio.kinds`` at import time (the kinds module imports
    ``_BaseDerivation`` from this module).
    """
    from .kinds._http import HTTPDerivation
    from .kinds._sql import SQLDerivation

    union = Annotated[
        Union[AIDerivation, ImportDerivation, SQLDerivation, HTTPDerivation],
        Field(discriminator="kind"),
    ]
    return TypeAdapter(union)


# Phase 1 typing surface remains the standard pair so existing isinstance
# checks compile; the runtime parser in :func:`load_derivation` consults
# the full extension union via :func:`_build_derivation_adapter`.
Derivation = Annotated[
    Union[AIDerivation, ImportDerivation],
    Field(discriminator="kind"),
]

_DerivationAdapter: TypeAdapter[Any] | None = None


def _adapter() -> TypeAdapter[Any]:
    global _DerivationAdapter
    if _DerivationAdapter is None:
        _DerivationAdapter = _build_derivation_adapter()
    return _DerivationAdapter


# --- public loaders --------------------------------------------------------


def load_derivation(path: Path) -> Derivation:
    """Load and validate a single ``derivations/<field>.yaml`` file."""
    if not path.is_file():
        raise DerivationError(f"derivation file not found: {path}")
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DerivationError(f"{path}: not valid YAML ({exc})") from exc
    if not isinstance(raw, dict):
        raise DerivationError(f"{path}: top-level value must be a mapping")
    if "kind" not in raw:
        raise DerivationError(f"{path}: missing required field 'kind'")
    try:
        return _adapter().validate_python(raw)
    except ValidationError as exc:
        raise DerivationError(f"{path}: {exc}") from exc


@dataclass
class DerivationFile:
    """A loaded derivation paired with the file it came from.

    Materialize loops use this to compute ``derivation_file_hash`` without
    re-walking the directory.
    """

    derivation: Derivation
    path: Path


def load_derivation_files(sheet_path: str | Path) -> list[DerivationFile]:
    """Load every ``derivations/*.yaml`` file with its source path.

    Returns the files in lexicographic filename order and rejects
    duplicate target declarations across files.
    """
    derivations_dir = Path(sheet_path) / "derivations"
    if not derivations_dir.is_dir():
        return []

    files: list[DerivationFile] = []
    declared_in: dict[str, Path] = {}
    for path in sorted(derivations_dir.glob("*.yaml")):
        derivation = load_derivation(path)
        for target in derivation.targets:
            if target in declared_in:
                raise DerivationError(
                    f"target {target!r} declared in both "
                    f"{declared_in[target]} and {path}"
                )
            declared_in[target] = path
        files.append(DerivationFile(derivation=derivation, path=path))
    return files


def load_derivations(sheet_path: str | Path) -> dict[str, Derivation]:
    """Load every ``derivations/*.yaml`` file under ``sheet_path``.

    Returns a mapping of ``target_field_name -> Derivation``. A derivation
    that declares multiple targets registers each target under the same
    instance. Missing ``derivations/`` directories return an empty dict.
    """
    derivations_dir = Path(sheet_path) / "derivations"
    if not derivations_dir.is_dir():
        return {}

    by_target: dict[str, Derivation] = {}
    declared_in: dict[str, Path] = {}
    for path in sorted(derivations_dir.glob("*.yaml")):
        derivation = load_derivation(path)
        for target in derivation.targets:
            if target in by_target:
                raise DerivationError(
                    f"target {target!r} declared in both "
                    f"{declared_in[target]} and {path}"
                )
            by_target[target] = derivation
            declared_in[target] = path
    return by_target


# --- DAG analysis ----------------------------------------------------------


def detect_cycles(by_target: dict[str, Derivation]) -> list[list[str]]:
    """Return cycles in the field-level ``target -> derived input`` DAG.

    Returns an empty list when the graph is acyclic.
    """
    cycles: list[list[str]] = []
    state: dict[str, str] = {}  # 'visiting' | 'done'

    def visit(node: str, path: list[str]) -> None:
        marker = state.get(node)
        if marker == "visiting":
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:] + [node])
            return
        if marker == "done":
            return
        state[node] = "visiting"
        path.append(node)
        derivation = by_target.get(node)
        if derivation is not None:
            for input_name in derivation.inputs:
                if input_name in by_target:
                    visit(input_name, path)
        path.pop()
        state[node] = "done"

    for target in sorted(by_target.keys()):
        if target not in state:
            visit(target, [])
    return cycles


def topological_sort(by_target: dict[str, Derivation]) -> list[str]:
    """Return targets in materialization order (deepest dependency first).

    Raises:
        DerivationError: when the graph contains a cycle.
    """
    cycles = detect_cycles(by_target)
    if cycles:
        formatted = "; ".join(" -> ".join(cycle) for cycle in cycles)
        raise DerivationError(f"derivation cycles detected: {formatted}")

    visited: set[str] = set()
    order: list[str] = []

    def visit(node: str) -> None:
        if node in visited:
            return
        visited.add(node)
        derivation = by_target.get(node)
        if derivation is not None:
            for input_name in derivation.inputs:
                if input_name in by_target:
                    visit(input_name)
        order.append(node)

    for target in sorted(by_target.keys()):
        visit(target)
    return order


def field_to_derivation(by_target: dict[str, Derivation]) -> dict[str, list[str]]:
    """Return a ``derivation_id -> targets`` reverse map for diagnostics."""
    grouped: dict[int, list[str]] = defaultdict(list)
    for target, derivation in by_target.items():
        grouped[id(derivation)].append(target)
    # Stable, human-readable mapping keyed by the joined target list.
    return {":".join(sorted(targets)): targets for targets in grouped.values()}


__all__ = [
    "AIDerivation",
    "Derivation",
    "DerivationError",
    "DerivationFile",
    "ImportDerivation",
    "MaterializationConfig",
    "detect_cycles",
    "field_to_derivation",
    "load_derivation",
    "load_derivation_files",
    "load_derivations",
    "topological_sort",
]
