"""Integration tests for the Sheet-level skills SDK surface."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from folio import SkillError, open_sheet

CONTRACT = dedent(
    """\
    apiVersion: v3.0.0
    kind: DataContract
    id: t
    name: t
    version: 1.0.0
    description: t
    schema:
      - name: items
        physicalType: jsonl
        properties:
          - name: id
            logicalType: string
            primaryKey: true
            required: true
    """
)


@pytest.fixture
def sheet_with_skills(tmp_path: Path):
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(CONTRACT)
    (sheet / "records.jsonl").write_text('{"id":"a"}\n')
    skills = sheet / "skills"
    skills.mkdir()
    (skills / "greet.md").write_text(
        dedent(
            """\
            ---
            name: greet
            description: Greet politely.
            arguments:
              - name: who
                required: true
            tools:
              - materialize
              - list_records
            ---
            Hello {who}!
            """
        )
    )
    (skills / "audit.md").write_text(
        dedent(
            """\
            ---
            name: audit
            description: Audit the records.
            ---
            Look at the records.
            """
        )
    )
    return open_sheet(sheet, actor="agent:test")


def test_list_skills_returns_sorted(sheet_with_skills) -> None:
    skills = sheet_with_skills.list_skills()
    assert [s.name for s in skills] == ["audit", "greet"]


def test_list_skills_validates_tool_names(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(CONTRACT)
    (sheet / "records.jsonl").write_text('{"id":"a"}\n')
    (sheet / "skills").mkdir()
    (sheet / "skills" / "bad.md").write_text(
        "---\nname: bad\ndescription: x\ntools: [no_such_method]\n---\nhi\n"
    )
    s = open_sheet(sheet, actor="agent:test")
    with pytest.raises(SkillError, match="not recognized SDK methods"):
        s.list_skills()


def test_get_skill_returns_none_when_missing(sheet_with_skills) -> None:
    assert sheet_with_skills.get_skill("ghost") is None


def test_get_skill_returns_parsed_skill(sheet_with_skills) -> None:
    skill = sheet_with_skills.get_skill("greet")
    assert skill is not None
    assert skill.name == "greet"
    assert skill.arguments[0].name == "who"


def test_render_skill_substitutes(sheet_with_skills) -> None:
    out = sheet_with_skills.render_skill("greet", {"who": "World"})
    assert out.strip() == "Hello World!"


def test_render_skill_missing_required_arg_raises(sheet_with_skills) -> None:
    with pytest.raises(SkillError, match="missing required arguments"):
        sheet_with_skills.render_skill("greet", {})


def test_render_skill_unknown_skill_raises(sheet_with_skills) -> None:
    with pytest.raises(SkillError, match="not found"):
        sheet_with_skills.render_skill("ghost")


def test_list_skills_empty_when_no_dir(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(CONTRACT)
    (sheet / "records.jsonl").write_text('{"id":"a"}\n')
    assert open_sheet(sheet, actor="agent:test").list_skills() == []


# --- Claude Skills export bridge ----------------------------------------


def test_export_claude_skills_emits_one_dir_per_skill(
    sheet_with_skills, tmp_path: Path
) -> None:
    from folio import export_claude_skills

    out = tmp_path / "out"
    written = export_claude_skills(sheet_with_skills.path, out)
    paths = sorted(p.relative_to(out).as_posix() for p in written)
    assert paths == [
        "t__audit/SKILL.md",
        "t__greet/SKILL.md",
    ]


def test_export_claude_skills_records_constraints(
    sheet_with_skills, tmp_path: Path
) -> None:
    from folio import export_claude_skills

    out = tmp_path / "out"
    export_claude_skills(sheet_with_skills.path, out)
    body = (out / "t__greet" / "SKILL.md").read_text()
    assert "name: t__greet" in body
    assert "description:" in body
    # Constraint section captures Folio-specific metadata.
    assert "Constraints (Folio metadata)" in body
    assert "Allowed SDK tools" in body
    assert "`materialize`" in body
    assert "`who` (required)" in body


def test_export_claude_skills_creates_out_dir(
    sheet_with_skills, tmp_path: Path
) -> None:
    from folio import export_claude_skills

    out = tmp_path / "deep" / "out"  # parents don't exist
    written = export_claude_skills(sheet_with_skills.path, out)
    assert out.is_dir()
    assert len(written) == 2
