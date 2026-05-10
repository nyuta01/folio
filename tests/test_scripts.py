"""Tests for ``folio.scripts`` (Phase 2 reusable-script runtime)."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from folio import ScriptError, ScriptResult, open_sheet
from folio.scripts import (
    SCRIPT_LANGUAGE_BY_EXTENSION,
    discover_scripts,
    run_script,
    runtime_root_for_sheet,
)


@pytest.fixture
def sheet_with_scripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            """
            apiVersion: v3.0.0
            kind: DataContract
            id: scripts-test-{uid}
            name: scripts-test
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

    scripts = sheet / "scripts"
    scripts.mkdir()
    (scripts / "hello.py").write_text(
        textwrap.dedent(
            """
            #!/usr/bin/env python3
            import sys
            print(f"hello from {sys.argv[1]} args={sys.argv[2:]}")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (scripts / "shout.sh").write_text(
        '#!/usr/bin/env bash\necho "shout: $1 $2"\n',
        encoding="utf-8",
    )
    (scripts / "shout.sh").chmod(0o755)

    # Hermetic runtime cache so tests don't pollute the real user cache.
    monkeypatch.setattr(
        "folio.scripts.runtime_root_for_sheet",
        lambda sheet_id: tmp_path / "runtime" / sheet_id,
    )
    return sheet


# --- discovery ------------------------------------------------------------


def test_discover_scripts_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    assert discover_scripts(sheet) == {}


def test_discover_scripts_indexes_python_and_shell(sheet_with_scripts: Path) -> None:
    discovered = discover_scripts(sheet_with_scripts)
    assert set(discovered.keys()) == {"hello", "shout"}
    assert discovered["hello"].suffix == ".py"
    assert discovered["shout"].suffix == ".sh"


def test_discover_scripts_ignores_unsupported_extensions(
    sheet_with_scripts: Path,
) -> None:
    (sheet_with_scripts / "scripts" / "ignored.txt").write_text("nope", encoding="utf-8")
    discovered = discover_scripts(sheet_with_scripts)
    assert "ignored" not in discovered


def test_discover_scripts_rejects_duplicate_basename(sheet_with_scripts: Path) -> None:
    (sheet_with_scripts / "scripts" / "hello.sh").write_text(
        "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
    )
    with pytest.raises(ScriptError, match="duplicate script basename"):
        discover_scripts(sheet_with_scripts)


# --- run_script -----------------------------------------------------------


def test_run_python_script(sheet_with_scripts: Path) -> None:
    result = run_script(
        sheet_with_scripts,
        "test-id",
        "hello",
        args=["one", "two"],
    )
    assert result.exit_code == 0
    assert "hello from" in result.stdout
    assert "args=['one', 'two']" in result.stdout
    assert isinstance(result, ScriptResult)


def test_run_shell_script(sheet_with_scripts: Path) -> None:
    result = run_script(
        sheet_with_scripts,
        "test-id",
        "shout",
        args=["echo-me"],
    )
    assert result.exit_code == 0
    assert "shout:" in result.stdout
    assert "echo-me" in result.stdout


def test_run_script_passes_sheet_path_as_first_argument(
    sheet_with_scripts: Path,
) -> None:
    result = run_script(sheet_with_scripts, "test-id", "hello")
    # sys.argv[1] is the sheet path; the script prints "hello from <path>".
    assert str(sheet_with_scripts) in result.stdout


def test_run_script_rejects_unknown_name(sheet_with_scripts: Path) -> None:
    with pytest.raises(ScriptError, match="not found"):
        run_script(sheet_with_scripts, "test-id", "ghost")


@pytest.mark.parametrize(
    "bad_name",
    ["../escape", "with space", "../../etc", "name/with/slash", ""],
)
def test_run_script_rejects_unsafe_name(
    sheet_with_scripts: Path, bad_name: str
) -> None:
    with pytest.raises(ScriptError, match="script name must match"):
        run_script(sheet_with_scripts, "test-id", bad_name)


def test_run_script_timeout_raises(sheet_with_scripts: Path) -> None:
    sleep = sheet_with_scripts / "scripts" / "sleep.sh"
    sleep.write_text(
        "#!/usr/bin/env bash\nsleep 5\n",
        encoding="utf-8",
    )
    sleep.chmod(0o755)

    with pytest.raises(ScriptError, match="timed out"):
        run_script(
            sheet_with_scripts,
            "test-id",
            "sleep",
            timeout_seconds=0.5,
        )


# --- runtime_root_for_sheet ----------------------------------------------


def test_runtime_root_for_sheet_lives_outside_repo() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    runtime = runtime_root_for_sheet("smoke-sheet")
    assert "folio" in str(runtime)
    assert "smoke-sheet" in str(runtime)
    try:
        runtime.relative_to(repo_root)
    except ValueError:
        return  # outside the repo as expected
    pytest.fail(f"runtime_root_for_sheet must live outside the repo, got {runtime}")


def test_supported_extensions_cover_python_and_shell() -> None:
    assert SCRIPT_LANGUAGE_BY_EXTENSION[".py"] == "python"
    assert SCRIPT_LANGUAGE_BY_EXTENSION[".sh"] == "shell"


# --- Sheet.run_script integration ----------------------------------------


def test_sheet_run_script_round_trip(sheet_with_scripts: Path) -> None:
    sheet = open_sheet(sheet_with_scripts)
    result = sheet.run_script("hello", args=["foo"])
    assert result.exit_code == 0
    assert "args=['foo']" in result.stdout
