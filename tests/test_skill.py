"""Tests for the per-sheet skills file format (folio._skill)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from folio import Skill, SkillError, load_skills, validate_skills_manifest

VALID_FRONTMATTER = dedent(
    """\
    ---
    name: refresh-revenue
    description: Re-run cross-sheet revenue lookup for stale records.
    audience: agent
    arguments:
      - name: only_country
        description: ISO-3166 alpha-2 code to scope the refresh.
        required: false
    tools:
      - materialize
      - list_records
    allowed_actors:
      - "agent:ops:*"
    ---

    # Refresh revenue

    Refresh `current_revenue_usd` for stale records.

    If `only_country` is supplied: filter by `country = '{only_country}'`.
    """
)


def _write(tmp_path: Path, name: str, body: str) -> Path:
    skills = tmp_path / "skills"
    skills.mkdir(exist_ok=True)
    path = skills / f"{name}.md"
    path.write_text(body, encoding="utf-8")
    return path


# ----------------------------------------------------------------------
# Parsing


def test_from_path_happy(tmp_path: Path) -> None:
    p = _write(tmp_path, "refresh-revenue", VALID_FRONTMATTER)
    skill = Skill.from_path(p)
    assert skill.name == "refresh-revenue"
    assert skill.audience == "agent"
    assert len(skill.arguments) == 1
    assert skill.arguments[0].name == "only_country"
    assert skill.tools == ["materialize", "list_records"]
    assert skill.allowed_actors == ["agent:ops:*"]
    assert "Refresh `current_revenue_usd`" in skill.body
    assert skill.body.lstrip().startswith("# Refresh revenue")


def test_audience_defaults_to_agent(tmp_path: Path) -> None:
    body = "---\nname: foo\ndescription: bar\n---\nhi\n"
    p = _write(tmp_path, "foo", body)
    skill = Skill.from_path(p)
    assert skill.audience == "agent"


# ----------------------------------------------------------------------
# Validation errors


def test_missing_frontmatter(tmp_path: Path) -> None:
    p = _write(tmp_path, "no-front", "Just a body, no frontmatter.")
    with pytest.raises(SkillError, match="missing YAML frontmatter"):
        Skill.from_path(p)


def test_bad_yaml(tmp_path: Path) -> None:
    body = "---\nname: foo\n  bad: indent\n---\nhi\n"
    p = _write(tmp_path, "foo", body)
    with pytest.raises(SkillError, match="invalid YAML frontmatter"):
        Skill.from_path(p)


def test_basename_mismatch(tmp_path: Path) -> None:
    body = "---\nname: bar\ndescription: x\n---\nhi\n"
    p = _write(tmp_path, "foo", body)
    with pytest.raises(SkillError, match="does not match file basename"):
        Skill.from_path(p)


def test_name_pattern(tmp_path: Path) -> None:
    body = "---\nname: BadName\ndescription: x\n---\nhi\n"
    p = _write(tmp_path, "BadName", body)
    with pytest.raises(SkillError, match="must match"):
        Skill.from_path(p)


def test_undeclared_argument_placeholder(tmp_path: Path) -> None:
    body = (
        "---\n"
        "name: foo\n"
        "description: x\n"
        "arguments:\n"
        "  - name: declared\n"
        "---\n"
        "Reads {declared} and also {missing}.\n"
    )
    p = _write(tmp_path, "foo", body)
    with pytest.raises(SkillError, match="undeclared argument placeholders"):
        Skill.from_path(p)


def test_unknown_audience(tmp_path: Path) -> None:
    body = "---\nname: foo\ndescription: x\naudience: alien\n---\nhi\n"
    p = _write(tmp_path, "foo", body)
    with pytest.raises(SkillError, match="schema error"):
        Skill.from_path(p)


def test_extra_top_level_key_rejected(tmp_path: Path) -> None:
    body = "---\nname: foo\ndescription: x\nrogue: 1\n---\nhi\n"
    p = _write(tmp_path, "foo", body)
    with pytest.raises(SkillError, match="schema error"):
        Skill.from_path(p)


# ----------------------------------------------------------------------
# Rendering


def test_render_substitutes_args(tmp_path: Path) -> None:
    p = _write(tmp_path, "refresh-revenue", VALID_FRONTMATTER)
    skill = Skill.from_path(p)
    rendered = skill.render({"only_country": "JP"})
    assert "country = 'JP'" in rendered


def test_render_leaves_unsupplied_optional_placeholders(tmp_path: Path) -> None:
    p = _write(tmp_path, "refresh-revenue", VALID_FRONTMATTER)
    skill = Skill.from_path(p)
    rendered = skill.render()
    assert "{only_country}" in rendered


def test_render_missing_required_argument_raises(tmp_path: Path) -> None:
    body = (
        "---\n"
        "name: foo\n"
        "description: x\n"
        "arguments:\n"
        "  - name: must_set\n"
        "    required: true\n"
        "---\n"
        "Uses {must_set}.\n"
    )
    p = _write(tmp_path, "foo", body)
    skill = Skill.from_path(p)
    with pytest.raises(SkillError, match="missing required arguments"):
        skill.render({})


# ----------------------------------------------------------------------
# Sheet-level loader


def test_load_skills_empty_when_no_dir(tmp_path: Path) -> None:
    assert load_skills(tmp_path) == []


def test_load_skills_returns_sorted(tmp_path: Path) -> None:
    _write(tmp_path, "zzz", "---\nname: zzz\ndescription: x\n---\nhi\n")
    _write(tmp_path, "aaa", "---\nname: aaa\ndescription: x\n---\nhi\n")
    skills = load_skills(tmp_path)
    assert [s.name for s in skills] == ["aaa", "zzz"]


def test_load_skills_rejects_unknown_tool(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "foo",
        "---\nname: foo\ndescription: x\ntools: [bogus_method]\n---\nhi\n",
    )
    with pytest.raises(SkillError, match="not recognized SDK methods"):
        load_skills(tmp_path, sdk_method_names={"materialize", "list_records"})


def test_load_skills_allows_known_tool(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "foo",
        "---\nname: foo\ndescription: x\ntools: [materialize]\n---\nhi\n",
    )
    skills = load_skills(tmp_path, sdk_method_names={"materialize"})
    assert [s.name for s in skills] == ["foo"]


def test_load_skills_skips_tool_check_when_none(tmp_path: Path) -> None:
    """When ``sdk_method_names=None`` the tools field is not cross-checked."""
    _write(
        tmp_path,
        "foo",
        "---\nname: foo\ndescription: x\ntools: [anything]\n---\nhi\n",
    )
    skills = load_skills(tmp_path)
    assert skills[0].tools == ["anything"]


# ----------------------------------------------------------------------
# README manifest cross-check


def test_validate_manifest_agrees(tmp_path: Path) -> None:
    _write(tmp_path, "foo", "---\nname: foo\ndescription: x\n---\nhi\n")
    _write(tmp_path, "bar", "---\nname: bar\ndescription: x\n---\nhi\n")
    assert validate_skills_manifest(tmp_path, ["foo", "bar"]) == []


def test_validate_manifest_extras_in_dir(tmp_path: Path) -> None:
    _write(tmp_path, "foo", "---\nname: foo\ndescription: x\n---\nhi\n")
    _write(tmp_path, "bar", "---\nname: bar\ndescription: x\n---\nhi\n")
    warnings = validate_skills_manifest(tmp_path, ["foo"])
    assert any("not listed" in w for w in warnings)


def test_validate_manifest_missing_from_dir(tmp_path: Path) -> None:
    _write(tmp_path, "foo", "---\nname: foo\ndescription: x\n---\nhi\n")
    warnings = validate_skills_manifest(tmp_path, ["foo", "ghost"])
    assert any("no matching skills" in w for w in warnings)


def test_validate_manifest_none_short_circuits(tmp_path: Path) -> None:
    _write(tmp_path, "foo", "---\nname: foo\ndescription: x\n---\nhi\n")
    assert validate_skills_manifest(tmp_path, None) == []
