"""Skill definitions packaged inside a Folio sheet.

A *skill* is a short, named markdown procedure that ships inside a
sheet's ``skills/`` directory. Skills are agent-facing operating
instructions — "fill missing customer industries", "refresh weekly
revenue", "review onboarding queue" — and travel with the sheet so a
recipient can pick up the right context when they ``tar``-extract it.

Design: see ``docs/methodology/sheet-skills-design.md``. The wire
format is a markdown file with YAML frontmatter; the body is plain
prose (no executable code paths). Side-effecting work goes through
derivations / SDK tools, which skills describe but don't execute.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .exceptions import SkillError

Audience = Literal["agent", "human", "both"]

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_ARG_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_FRONTMATTER_RE = re.compile(r"\A\s*---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
_PLACEHOLDER_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")


class SkillArgument(BaseModel):
    """A named argument that may be substituted into the skill body."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    description: str | None = None
    required: bool = False


class Skill(BaseModel):
    """A skill loaded from ``skills/<name>.md``.

    Construct via ``Skill.from_path``; do not instantiate directly
    unless you have already validated the source.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    description: str
    audience: Audience = "agent"
    arguments: list[SkillArgument] = Field(default_factory=list)
    tools: list[str] | None = None
    allowed_actors: list[str] | None = None
    body: str = ""
    """The markdown body, frontmatter stripped, leading whitespace trimmed."""

    # -----------------------------------------------------------------
    # Loading

    @classmethod
    def from_path(cls, path: str | Path) -> Skill:
        """Parse ``skills/<name>.md`` into a validated ``Skill``.

        Raises :class:`SkillError` on any failure: missing frontmatter,
        malformed YAML, schema mismatch, or basename / name disagreement.
        """
        p = Path(path)
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError as exc:
            raise SkillError(f"{p}: cannot read: {exc}") from exc

        m = _FRONTMATTER_RE.match(raw)
        if not m:
            raise SkillError(
                f"{p}: missing YAML frontmatter; expected `---` ... `---` at top"
            )

        try:
            front: Any = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as exc:
            raise SkillError(f"{p}: invalid YAML frontmatter: {exc}") from exc

        if not isinstance(front, dict):
            raise SkillError(f"{p}: frontmatter must be a YAML mapping")

        body = m.group(2).lstrip("\n")

        # Pydantic catches schema errors; we add basename + name agreement and
        # placeholder reachability afterwards.
        try:
            skill = cls.model_validate({**front, "body": body})
        except ValidationError as exc:
            raise SkillError(f"{p}: schema error: {exc.errors()}") from exc

        if not _NAME_RE.fullmatch(skill.name):
            raise SkillError(
                f"{p}: skill name {skill.name!r} must match {_NAME_RE.pattern}"
            )

        basename = p.stem
        if skill.name != basename:
            raise SkillError(
                f"{p}: frontmatter name {skill.name!r} does not match file basename "
                f"{basename!r}"
            )

        for arg in skill.arguments:
            if not _ARG_NAME_RE.fullmatch(arg.name):
                raise SkillError(
                    f"{p}: argument name {arg.name!r} must match "
                    f"{_ARG_NAME_RE.pattern}"
                )

        declared = {a.name for a in skill.arguments}
        used = set(_PLACEHOLDER_RE.findall(body))
        undeclared = used - declared
        if undeclared:
            raise SkillError(
                f"{p}: body uses undeclared argument placeholders "
                f"{sorted(undeclared)} — declare them under `arguments:` or "
                "remove the braces"
            )

        if skill.allowed_actors is not None:
            for pattern in skill.allowed_actors:
                try:
                    fnmatch.translate(pattern)
                except Exception as exc:  # pragma: no cover — translate ~never errs
                    raise SkillError(
                        f"{p}: allowed_actors pattern {pattern!r} is malformed: {exc}"
                    ) from exc

        return skill

    # -----------------------------------------------------------------
    # Rendering

    def render(self, args: dict[str, Any] | None = None) -> str:
        """Return the body with ``{name}`` placeholders substituted.

        Raises :class:`SkillError` if a required argument is missing.
        Extra keys in ``args`` are ignored.
        """
        supplied = dict(args or {})
        missing = [a.name for a in self.arguments if a.required and a.name not in supplied]
        if missing:
            raise SkillError(
                f"skill {self.name!r}: missing required arguments {missing}"
            )

        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            if key in supplied:
                return str(supplied[key])
            # Unrequired and not supplied → leave placeholder visible so the
            # consumer can fill it later without silent drops.
            return m.group(0)

        return _PLACEHOLDER_RE.sub(repl, self.body)


# ----------------------------------------------------------------------
# Sheet-level loader


def load_skills(
    sheet_path: str | Path,
    *,
    sdk_method_names: set[str] | None = None,
) -> list[Skill]:
    """Load every ``skills/*.md`` under a sheet, sorted by name.

    The ``sdk_method_names`` allow-list is checked against each skill's
    ``tools`` field. Pass the actual SDK method surface so the
    validation tracks the implementation.

    Raises :class:`SkillError` on the first invalid file.
    """
    root = Path(sheet_path)
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return []

    skills: list[Skill] = []
    seen: set[str] = set()

    for path in sorted(skills_dir.glob("*.md")):
        skill = Skill.from_path(path)
        if skill.name in seen:
            raise SkillError(
                f"{path}: duplicate skill name {skill.name!r}; basenames must be unique"
            )
        seen.add(skill.name)

        if sdk_method_names is not None and skill.tools:
            unknown = [t for t in skill.tools if t not in sdk_method_names]
            if unknown:
                raise SkillError(
                    f"{path}: tools {unknown!r} are not recognized SDK methods"
                )

        skills.append(skill)

    return skills


def export_claude_skills(
    sheet_path: str | Path,
    out_dir: str | Path,
) -> list[Path]:
    """Emit a Claude-Code-compatible ``SKILL.md`` per discovered skill.

    For a sheet with id ``my-sheet`` and a skill ``foo``, writes
    ``<out_dir>/my-sheet__foo/SKILL.md`` whose frontmatter contains the
    keys Claude Skills recognizes (``name``, ``description``) plus a
    "Constraints" section for Folio-specific metadata (``tools``,
    ``allowed_actors``, ``audience``).

    The bridge is **derived, read-only output** — the sheet's
    ``skills/`` directory is always the source of truth. Re-run the
    export whenever you change a skill.

    Returns the list of written ``SKILL.md`` paths.
    """
    from .contract import load_contract

    root = Path(sheet_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    contract = load_contract(root)
    skills = load_skills(root)

    written: list[Path] = []
    for skill in skills:
        skill_dir = out / f"{contract.id}__{skill.name}"
        skill_dir.mkdir(parents=True, exist_ok=True)
        target = skill_dir / "SKILL.md"

        frontmatter_lines = [
            "---",
            f"name: {contract.id}__{skill.name}",
            f"description: {_format_yaml_block(skill.description)}",
            "---",
        ]

        body_parts = [skill.body.rstrip()]
        constraints: list[str] = []
        if skill.audience != "agent":
            constraints.append(f"- **Audience**: `{skill.audience}`")
        if skill.tools:
            constraints.append(
                "- **Allowed SDK tools**: " + ", ".join(f"`{t}`" for t in skill.tools)
            )
        if skill.allowed_actors:
            constraints.append(
                "- **Allowed actors** (`fnmatch`): "
                + ", ".join(f"`{p}`" for p in skill.allowed_actors)
            )
        if skill.arguments:
            constraints.append("- **Arguments**:")
            for arg in skill.arguments:
                req = " (required)" if arg.required else ""
                desc = f" — {arg.description}" if arg.description else ""
                constraints.append(f"  - `{arg.name}`{req}{desc}")

        if constraints:
            body_parts.append("")
            body_parts.append("## Constraints (Folio metadata)")
            body_parts.append("")
            body_parts.extend(constraints)

        content = "\n".join(frontmatter_lines) + "\n\n" + "\n".join(body_parts) + "\n"
        target.write_text(content, encoding="utf-8")
        written.append(target)

    return written


def _format_yaml_block(text: str) -> str:
    """Quote a description string so YAML round-trips losslessly.

    Multi-line descriptions become folded block scalars; single-line
    descriptions become double-quoted strings with embedded quotes
    escaped. Keeps the Claude-side parser happy.
    """
    if "\n" in text:
        body = text.replace("\n", "\n  ")
        return f">-\n  {body}"
    return '"' + text.replace('"', '\\"') + '"'


def validate_skills_manifest(
    sheet_path: str | Path,
    manifest: list[str] | None,
) -> list[str]:
    """Cross-check the README ``agent_skills`` manifest against ``skills/``.

    Returns a list of warning strings (never raises). An empty list
    means the manifest agrees with the directory.
    """
    if manifest is None:
        return []

    root = Path(sheet_path)
    skills_dir = root / "skills"
    on_disk = (
        {p.stem for p in skills_dir.glob("*.md")} if skills_dir.is_dir() else set()
    )
    manifested = set(manifest)

    warnings: list[str] = []
    missing = manifested - on_disk
    if missing:
        warnings.append(
            "agent_skills manifest lists "
            f"{sorted(missing)} but no matching skills/*.md was found"
        )
    extras = on_disk - manifested
    if extras:
        warnings.append(
            f"skills/ contains {sorted(extras)} which are not listed in the "
            "README `agent_skills` manifest"
        )
    return warnings
