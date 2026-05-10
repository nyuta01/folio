"""Tests for ``folio.derivation`` (Phase 1 derivation parsing + DAG)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from folio import (
    AIDerivation,
    DerivationError,
    ImportDerivation,
    detect_cycles,
    load_derivation,
    load_derivations,
    topological_sort,
)


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return path


# --- ai kind ---------------------------------------------------------------


def test_minimal_ai_derivation_loads(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "industry_tag.yaml",
        """
        targets: [industry_tag]
        inputs: [company_name]
        kind: ai
        model: claude-sonnet-4-6
        prompt: |
          Industry of {{ company_name }} in one word.
        output: text
        """,
    )

    derivation = load_derivation(path)

    assert isinstance(derivation, AIDerivation)
    assert derivation.targets == ["industry_tag"]
    assert derivation.inputs == ["company_name"]
    assert derivation.model == "claude-sonnet-4-6"
    assert derivation.output == "text"
    assert derivation.materialization.respect_human_override is True


def test_multi_target_ai_with_output_schema(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "company_facts.yaml",
        """
        targets: [industry_tag, employee_size]
        inputs: [company_name]
        kind: ai
        model: claude-sonnet-4-6
        prompt: "x"
        output: json
        output_schema:
          industry_tag: string
          employee_size: string
        """,
    )

    derivation = load_derivation(path)

    assert isinstance(derivation, AIDerivation)
    assert derivation.output_schema == {
        "industry_tag": "string",
        "employee_size": "string",
    }


def test_multi_target_ai_without_output_schema_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a, b]
        kind: ai
        model: m
        prompt: x
        output: json
        """,
    )

    with pytest.raises(DerivationError, match="output_schema"):
        load_derivation(path)


def test_multi_target_ai_text_output_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a, b]
        kind: ai
        model: m
        prompt: x
        output: text
        """,
    )

    with pytest.raises(DerivationError, match="output='json'"):
        load_derivation(path)


def test_output_schema_keys_must_match_targets(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a, b]
        kind: ai
        model: m
        prompt: x
        output: json
        output_schema:
          a: string
          c: string
        """,
    )

    with pytest.raises(DerivationError, match="output_schema keys"):
        load_derivation(path)


def test_single_target_ai_must_not_declare_output_schema(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a]
        kind: ai
        model: m
        prompt: x
        output: text
        output_schema:
          a: string
        """,
    )

    with pytest.raises(DerivationError, match="must not declare output_schema"):
        load_derivation(path)


def test_prompt_and_prompt_ref_collision_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a]
        kind: ai
        model: m
        prompt: x
        prompt_ref: prompts/a.md
        output: text
        """,
    )

    with pytest.raises(DerivationError, match="exactly one of 'prompt' or 'prompt_ref'"):
        load_derivation(path)


def test_prompt_source_missing_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a]
        kind: ai
        model: m
        output: text
        """,
    )

    with pytest.raises(DerivationError, match="exactly one of 'prompt' or 'prompt_ref'"):
        load_derivation(path)


# --- import kind -----------------------------------------------------------


def test_single_target_import_with_value_field(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "legacy_id.yaml",
        """
        targets: [legacy_id]
        inputs: []
        kind: import
        source: legacy/customer_mapping.csv
        key_field: id
        value_field: legacy_customer_id
        """,
    )

    derivation = load_derivation(path)

    assert isinstance(derivation, ImportDerivation)
    assert derivation.value_field == "legacy_customer_id"
    assert derivation.value_fields is None


def test_multi_target_import_with_value_fields(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "facts.yaml",
        """
        targets: [industry_tag, hq_country]
        kind: import
        source: refs/customers.csv
        key_field: id
        value_fields:
          industry_tag: industry_tag
          hq_country: headquarters_country
        """,
    )

    derivation = load_derivation(path)

    assert isinstance(derivation, ImportDerivation)
    assert derivation.value_fields == {
        "industry_tag": "industry_tag",
        "hq_country": "headquarters_country",
    }


def test_import_value_field_and_value_fields_collision(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a]
        kind: import
        source: x.csv
        key_field: id
        value_field: a
        value_fields:
          a: a
        """,
    )

    with pytest.raises(DerivationError, match="exactly one of 'value_field' or 'value_fields'"):
        load_derivation(path)


def test_multi_target_import_without_value_fields_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a, b]
        kind: import
        source: x.csv
        key_field: id
        value_field: a
        """,
    )

    with pytest.raises(DerivationError, match="multi-target import"):
        load_derivation(path)


def test_multi_target_import_value_fields_keys_must_match_targets(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a, b]
        kind: import
        source: x.csv
        key_field: id
        value_fields:
          a: src_a
          c: src_c
        """,
    )

    with pytest.raises(DerivationError, match="keys must equal targets"):
        load_derivation(path)


# --- generic --------------------------------------------------------------


def test_unknown_kind_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a]
        kind: voodoo
        """,
    )

    with pytest.raises(DerivationError):
        load_derivation(path)


def test_invalid_yaml_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("not: valid: yaml:", encoding="utf-8")

    with pytest.raises(DerivationError, match="not valid YAML"):
        load_derivation(path)


def test_extra_attribute_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad.yaml",
        """
        targets: [a]
        kind: ai
        model: m
        prompt: x
        output: text
        unexpected: attr
        """,
    )

    with pytest.raises(DerivationError):
        load_derivation(path)


def test_load_derivations_empty_directory_returns_empty_dict(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    assert load_derivations(sheet) == {}


def test_load_derivations_indexes_each_target(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet"
    derivations_dir = sheet / "derivations"
    derivations_dir.mkdir(parents=True)
    _write(
        derivations_dir / "industry_tag.yaml",
        """
        targets: [industry_tag]
        inputs: [company_name]
        kind: ai
        model: m
        prompt: x
        output: text
        """,
    )
    _write(
        derivations_dir / "company_facts.yaml",
        """
        targets: [employee_size, hq_country]
        inputs: [company_name]
        kind: ai
        model: m
        prompt: x
        output: json
        output_schema:
          employee_size: string
          hq_country: string
        """,
    )

    by_target = load_derivations(sheet)

    assert set(by_target.keys()) == {"industry_tag", "employee_size", "hq_country"}
    # The two-target derivation is shared between its two targets.
    assert by_target["employee_size"] is by_target["hq_country"]


def test_duplicate_target_across_files_rejected(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet"
    derivations_dir = sheet / "derivations"
    derivations_dir.mkdir(parents=True)
    _write(
        derivations_dir / "first.yaml",
        """
        targets: [tag]
        kind: ai
        model: m
        prompt: x
        output: text
        """,
    )
    _write(
        derivations_dir / "second.yaml",
        """
        targets: [tag]
        kind: ai
        model: m
        prompt: y
        output: text
        """,
    )

    with pytest.raises(DerivationError, match="declared in both"):
        load_derivations(sheet)


# --- DAG analysis ----------------------------------------------------------


def _make_derivation(targets: list[str], inputs: list[str]) -> AIDerivation:
    return AIDerivation(
        targets=targets,
        inputs=inputs,
        kind="ai",
        model="m",
        prompt="x",
        output="text",
        output_schema=(
            {target: "string" for target in targets} if len(targets) >= 2 else None
        ),
    )


def test_detect_cycles_returns_empty_for_acyclic_graph() -> None:
    by_target = {
        "a": _make_derivation(["a"], ["raw"]),
        "b": _make_derivation(["b"], ["a"]),
        "c": _make_derivation(["c"], ["b"]),
    }
    assert detect_cycles(by_target) == []


def test_detect_cycles_finds_two_node_cycle() -> None:
    by_target = {
        "a": _make_derivation(["a"], ["b"]),
        "b": _make_derivation(["b"], ["a"]),
    }
    cycles = detect_cycles(by_target)
    assert cycles
    cycle = cycles[0]
    assert set(cycle[:-1]) == {"a", "b"}
    assert cycle[0] == cycle[-1]


def test_topological_sort_returns_inputs_first() -> None:
    by_target = {
        "a": _make_derivation(["a"], ["raw"]),
        "b": _make_derivation(["b"], ["a"]),
        "c": _make_derivation(["c"], ["b"]),
    }
    order = topological_sort(by_target)

    assert order.index("a") < order.index("b") < order.index("c")


def test_topological_sort_raises_on_cycle() -> None:
    by_target = {
        "a": _make_derivation(["a"], ["b"]),
        "b": _make_derivation(["b"], ["a"]),
    }
    with pytest.raises(DerivationError, match="cycles detected"):
        topological_sort(by_target)


def test_topological_sort_ignores_non_derived_inputs() -> None:
    by_target = {
        "tag": _make_derivation(["tag"], ["company_name"]),
    }
    assert topological_sort(by_target) == ["tag"]
