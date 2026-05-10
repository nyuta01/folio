"""Phase 2 ``README.md`` YAML frontmatter parser.

A sheet may begin its ``README.md`` with a YAML frontmatter block
delimited by ``---`` lines. The block surfaces AI-oriented metadata
(purpose, default actor, tags, links, agent_skills) for agents that
read sheets directly without going through the SDK.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from .exceptions import FolioError


class ReadmeError(FolioError):
    """Raised when ``README.md`` frontmatter is malformed or invalid."""


_FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


class Frontmatter(BaseModel):
    """Validated AI-oriented sheet metadata."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    purpose: str
    default_actor: str
    tags: list[str] | None = None
    links: dict[str, str] | None = None
    agent_skills: list[str] | None = None


def parse_frontmatter(text: str) -> Frontmatter | None:
    """Extract and validate the YAML frontmatter from a README body.

    Returns ``None`` when the body does not begin with a ``---`` line.
    Raises :class:`ReadmeError` when the delimiter is malformed, the
    YAML is invalid, or the model fails validation.
    """
    if not text.startswith("---"):
        return None

    match = _FRONTMATTER_PATTERN.match(text)
    if match is None:
        raise ReadmeError(
            "README.md frontmatter delimiter is malformed; "
            "expected '---' followed by a closing '---'"
        )

    block = match.group(1)
    try:
        data: Any = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise ReadmeError(f"frontmatter is not valid YAML: {exc}") from exc
    if data is None:
        raise ReadmeError("frontmatter must declare 'purpose' and 'default_actor'")
    if not isinstance(data, dict):
        raise ReadmeError("frontmatter top-level value must be a mapping")

    try:
        return Frontmatter.model_validate(data)
    except ValidationError as exc:
        raise ReadmeError(f"frontmatter is invalid: {exc}") from exc


def load_readme_metadata(sheet_path: str | Path) -> Frontmatter | None:
    """Load and validate ``<sheet>/README.md`` frontmatter.

    Returns ``None`` when ``README.md`` is missing, contains no
    frontmatter block, or has an empty body.
    """
    readme = Path(sheet_path) / "README.md"
    if not readme.is_file():
        return None
    text = readme.read_text(encoding="utf-8")
    if not text:
        return None
    return parse_frontmatter(text)


__all__ = [
    "Frontmatter",
    "ReadmeError",
    "load_readme_metadata",
    "parse_frontmatter",
]
