"""Tests for ``folio.readme`` (Phase 2 README YAML frontmatter)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from folio import (
    Frontmatter,
    ReadmeError,
    load_readme_metadata,
    open_sheet,
    parse_frontmatter,
)
from folio.cli import app


_BASE_README = textwrap.dedent(
    """
    ---
    purpose: customer enrichment master
    default_actor: agent:enrichment
    tags: [phase-1, sales]
    links:
      contract: contract.yaml
      docs: ../docs/customers.md
    ---

    # Customers

    The body of the README is human-readable.
    """
).strip()


def test_parse_frontmatter_returns_none_when_absent() -> None:
    assert parse_frontmatter("# Title\n\nNo frontmatter here.\n") is None


def test_parse_frontmatter_minimal_valid() -> None:
    body = textwrap.dedent(
        """
        ---
        purpose: minimal
        default_actor: agent:bot
        ---

        body
        """
    ).strip()
    metadata = parse_frontmatter(body)
    assert isinstance(metadata, Frontmatter)
    assert metadata.purpose == "minimal"
    assert metadata.default_actor == "agent:bot"
    assert metadata.tags is None


def test_parse_frontmatter_full() -> None:
    metadata = parse_frontmatter(_BASE_README)
    assert metadata is not None
    assert metadata.tags == ["phase-1", "sales"]
    assert metadata.links == {
        "contract": "contract.yaml",
        "docs": "../docs/customers.md",
    }


def test_parse_frontmatter_missing_required_field_rejected() -> None:
    body = textwrap.dedent(
        """
        ---
        purpose: missing-actor
        ---
        """
    ).strip()
    with pytest.raises(ReadmeError, match="default_actor"):
        parse_frontmatter(body)


def test_parse_frontmatter_unknown_attribute_rejected() -> None:
    body = textwrap.dedent(
        """
        ---
        purpose: ok
        default_actor: agent:bot
        weird: nope
        ---
        """
    ).strip()
    with pytest.raises(ReadmeError, match="invalid"):
        parse_frontmatter(body)


def test_parse_frontmatter_missing_closing_delimiter_rejected() -> None:
    body = textwrap.dedent(
        """
        ---
        purpose: dangling
        default_actor: agent:bot
        """
    ).strip()
    with pytest.raises(ReadmeError, match="delimiter"):
        parse_frontmatter(body)


def test_parse_frontmatter_invalid_yaml_rejected() -> None:
    body = "---\nnot: valid: yaml:\n---\n"
    with pytest.raises(ReadmeError, match="not valid YAML"):
        parse_frontmatter(body)


def test_parse_frontmatter_empty_body_rejected() -> None:
    with pytest.raises(ReadmeError, match="declare 'purpose'"):
        parse_frontmatter("---\n\n---\n")


# --- load_readme_metadata + Sheet integration ----------------------------


@pytest.fixture
def sheet_with_readme(tmp_path: Path) -> Path:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            """
            apiVersion: v3.0.0
            kind: DataContract
            id: readme-test-{uid}
            name: readme-test
            version: 1.0.0
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
        .strip()
        .replace("{uid}", tmp_path.name),
        encoding="utf-8",
    )
    (sheet / "records.jsonl").write_text("", encoding="utf-8")
    return sheet


def test_load_readme_metadata_missing_returns_none(sheet_with_readme: Path) -> None:
    assert load_readme_metadata(sheet_with_readme) is None


def test_load_readme_metadata_without_frontmatter_returns_none(
    sheet_with_readme: Path,
) -> None:
    (sheet_with_readme / "README.md").write_text(
        "# Title\n\nbody\n", encoding="utf-8"
    )
    assert load_readme_metadata(sheet_with_readme) is None


def test_load_readme_metadata_returns_validated(sheet_with_readme: Path) -> None:
    (sheet_with_readme / "README.md").write_text(_BASE_README + "\n", encoding="utf-8")
    metadata = load_readme_metadata(sheet_with_readme)
    assert metadata is not None
    assert metadata.purpose == "customer enrichment master"


def test_sheet_metadata_property(sheet_with_readme: Path) -> None:
    (sheet_with_readme / "README.md").write_text(_BASE_README + "\n", encoding="utf-8")
    sheet = open_sheet(sheet_with_readme)
    metadata = sheet.metadata
    assert metadata is not None
    assert metadata.default_actor == "agent:enrichment"


# --- folio validate CLI integration --------------------------------------


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def test_validate_without_readme_succeeds(
    cli_runner: CliRunner, sheet_with_readme: Path
) -> None:
    result = cli_runner.invoke(app, ["validate", str(sheet_with_readme)])
    assert result.exit_code == 0
    assert "contract.yaml is valid" in result.stdout
    # No frontmatter line because no README.
    assert "frontmatter" not in result.stdout


def test_validate_reports_valid_frontmatter(
    cli_runner: CliRunner, sheet_with_readme: Path
) -> None:
    (sheet_with_readme / "README.md").write_text(_BASE_README + "\n", encoding="utf-8")
    result = cli_runner.invoke(app, ["validate", str(sheet_with_readme)])
    assert result.exit_code == 0
    assert "README.md frontmatter is valid" in result.stdout
    assert "purpose: customer enrichment master" in result.stdout


def test_validate_warns_on_malformed_frontmatter_by_default(
    cli_runner: CliRunner, sheet_with_readme: Path
) -> None:
    (sheet_with_readme / "README.md").write_text(
        "---\nnot: valid: yaml:\n---\n", encoding="utf-8"
    )
    result = cli_runner.invoke(app, ["validate", str(sheet_with_readme)])
    assert result.exit_code == 0
    assert "warning:" in result.stderr


def test_validate_strict_fails_on_malformed_frontmatter(
    cli_runner: CliRunner, sheet_with_readme: Path
) -> None:
    (sheet_with_readme / "README.md").write_text(
        "---\nnot: valid: yaml:\n---\n", encoding="utf-8"
    )
    result = cli_runner.invoke(
        app, ["validate", str(sheet_with_readme), "--strict"]
    )
    assert result.exit_code != 0
    assert "error:" in result.stderr
