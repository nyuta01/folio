#!/usr/bin/env python3
"""Validate Folio plan/failure-log drift invariants.

Run as `python3 scripts/harness_drift.py` from the repository root, or via
`make drift-check`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def exists(relative: str) -> bool:
    return (ROOT / relative).exists()


REQUIRED_SELF_IMPROVEMENT_FILES = [
    "docs/QUALITY_SCORE.md",
    "docs/agent-failures.md",
    "docs/methodology/permanent-fix-protocol.md",
    "docs/methodology/self-pdca-loop.md",
    "scripts/harness_drift.py",
    "scripts/harness_check.py",
    "scripts/validate_docs.py",
]

for relative in REQUIRED_SELF_IMPROVEMENT_FILES:
    if not exists(relative):
        fail(f"missing self-improvement file: {relative}")


feature_list: dict | None = None
try:
    feature_list = json.loads(read_text("docs/exec-plans/feature-list.json"))
except FileNotFoundError:
    fail("cannot read feature-list.json: file is missing")
except json.JSONDecodeError as exc:
    fail(f"cannot read feature-list.json: {exc}")


def validate_plan_pdca_sections(relative_plan_path: str) -> None:
    text = read_text(relative_plan_path)
    for heading in (
        "## Observation",
        "## Decision",
        "## Permanent Fix",
        "## Next Check",
    ):
        if heading not in text:
            fail(f"{relative_plan_path}: missing required PDCA section {heading}")


def validate_quality_score(tasks: list[dict]) -> None:
    if not exists("docs/QUALITY_SCORE.md"):
        return

    task_ids = {task.get("id") for task in tasks if task.get("id")}
    text = read_text("docs/QUALITY_SCORE.md")
    rows = [line for line in text.split("\n") if line.startswith("|") and "---" not in line]

    domain_rows = 0
    for row in rows:
        cells = [cell.strip() for cell in row.split("|")[1:-1]]
        if len(cells) < 5 or cells[0] == "Domain":
            continue

        domain_rows += 1
        domain, score_text, _evidence, _weak_spot, next_task = cells[:5]
        try:
            score = int(score_text)
        except ValueError:
            fail(f"QUALITY_SCORE.md: {domain} has invalid score {score_text!r}")
            continue
        if score < 1 or score > 5:
            fail(f"QUALITY_SCORE.md: {domain} score {score} must be in 1..5")
            continue

        if score <= 2:
            match = re.search(r"`([^`]+)`", next_task)
            if not match:
                fail(f"QUALITY_SCORE.md: {domain} score {score} must name a next task")
                continue
            if match.group(1) not in task_ids:
                fail(
                    f"QUALITY_SCORE.md: {domain} references unknown next task "
                    f"{match.group(1)}"
                )

    if domain_rows == 0:
        fail("QUALITY_SCORE.md must contain at least one scored domain row")


def strip_fenced_code(text: str) -> str:
    return re.sub(r"```[\s\S]*?```", "", text)


def validate_failure_log(tasks: list[dict]) -> None:
    if not exists("docs/agent-failures.md"):
        return

    task_ids = {task.get("id") for task in tasks if task.get("id")}
    failure_log = strip_fenced_code(read_text("docs/agent-failures.md"))
    failure_entries = re.split(r"^## ", failure_log, flags=re.MULTILINE)[1:]

    seen_ids: set[str] = set()
    allowed_statuses = {
        "observing",
        "needs-fix",
        "fixed",
        "archived",
        "fixed-but-regressing",
    }

    for entry in failure_entries:
        heading_line, _, body = entry.partition("\n")
        id_match = re.match(r"^(F-\d{3})\b", heading_line)
        if not id_match:
            continue

        failure_id = id_match.group(1)
        if failure_id in seen_ids:
            fail(f"{failure_id}: duplicate failure id")
        seen_ids.add(failure_id)

        status_match = re.search(r"- \*\*Status\*\*: `?([a-z-]+)`?", body)
        if not status_match:
            fail(f"{failure_id}: missing status")
            continue

        status = status_match.group(1)
        if status not in allowed_statuses:
            fail(f"{failure_id}: invalid failure status {status}")

        task_match = re.search(r"- \*\*Task\*\*: `([^`]+)`", body)
        if not task_match:
            fail(f"{failure_id}: missing linked task")
        elif task_match.group(1) not in task_ids:
            fail(f"{failure_id}: references unknown task {task_match.group(1)}")

        plan_match = re.search(r"- \*\*Plan\*\*: `([^`]+)`", body)
        if not plan_match:
            fail(f"{failure_id}: missing linked plan")
        elif not exists(plan_match.group(1)):
            fail(f"{failure_id}: references missing plan {plan_match.group(1)}")

        if status == "needs-fix":
            fail(
                f"{failure_id}: status is needs-fix; resolve the permanent-fix "
                "task before verification can pass"
            )

        if (
            status == "fixed"
            and "**Permanent fix**" not in body
            and "### Permanent fix" not in body
        ):
            fail(f"{failure_id}: fixed failures must describe the permanent fix")


if feature_list is not None and isinstance(feature_list.get("tasks"), list):
    tasks = feature_list["tasks"]
    task_ids = {task.get("id") for task in tasks if task.get("id")}
    plan_urls = {
        task.get("plan_url")
        for task in tasks
        if isinstance(task.get("plan_url"), str)
    }

    for task in tasks:
        for dep in task.get("depends", []) or []:
            if dep not in task_ids:
                fail(f"{task.get('id')}: dependency references unknown task {dep}")

        if task.get("status") in ("done", "in_progress") and not task.get("plan_url"):
            fail(f"{task.get('id')}: active or completed task must have a plan_url")

        if task.get("status") == "done" and not (task.get("paths") or []):
            fail(f"{task.get('id')}: completed task must list affected paths")

    active_plans_dir = ROOT / "docs/exec-plans/active"
    if active_plans_dir.exists():
        for entry in sorted(active_plans_dir.iterdir()):
            if entry.name == "README.md" or entry.suffix != ".md":
                continue
            relative_plan_path = f"docs/exec-plans/active/{entry.name}"
            if relative_plan_path not in plan_urls:
                fail(
                    f"{relative_plan_path}: active plan is not referenced by "
                    "feature-list"
                )
            validate_plan_pdca_sections(relative_plan_path)

    has_permanent_fix_task = any(
        "permanent-fix" in f"{task.get('id', '')} {task.get('title', '')}".lower()
        for task in tasks
    )
    has_self_pdca_task = any(
        "pdca" in f"{task.get('id', '')} {task.get('title', '')}".lower()
        for task in tasks
    )
    if not has_permanent_fix_task:
        fail("feature-list must track the permanent-fix loop")
    if not has_self_pdca_task:
        fail("feature-list must track the self-PDCA loop")

    validate_quality_score(tasks)


def validate_adr_anchored_invariants() -> None:
    """Reject silent drift away from ADR-anchored implementation choices."""
    src_dir = ROOT / "src" / "folio"
    if not src_dir.is_dir():
        return

    src_files = sorted(src_dir.rglob("*.py"))

    # ADR-0009: anthropic must be imported only in _ai_kind.py.
    anthropic_pattern = re.compile(
        r"^\s*(import\s+anthropic|from\s+anthropic\b)", re.MULTILINE
    )
    for path in src_files:
        if path.name == "_ai_kind.py":
            continue
        text = path.read_text(encoding="utf-8")
        if anthropic_pattern.search(text):
            fail(
                f"{path.relative_to(ROOT)}: anthropic must be imported only "
                "in src/folio/_ai_kind.py per ADR-0009"
            )

    # FastAPI / uvicorn are Phase 5 Viewer dependencies and must not leak
    # into the SDK or the MCP server. Both ship under src/folio_viewer/.
    viewer_only = re.compile(
        r"^\s*(import\s+(fastapi|uvicorn)|from\s+(fastapi|uvicorn)\b)",
        re.MULTILINE,
    )
    for module_dir in ("folio", "folio_mcp"):
        module_root = ROOT / "src" / module_dir
        if not module_root.is_dir():
            continue
        for path in sorted(module_root.rglob("*.py")):
            if viewer_only.search(path.read_text(encoding="utf-8")):
                fail(
                    f"{path.relative_to(ROOT)}: fastapi / uvicorn may only "
                    "be imported from src/folio_viewer/"
                )

    # ADR-0005: DuckDB must remain in use somewhere under src/folio/.
    if not _any_module_imports(src_files, "duckdb"):
        fail("ADR-0005 anchor: no module under src/folio/ imports duckdb")

    # ADR-0006: filelock must remain in use somewhere under src/folio/.
    if not _any_module_imports(src_files, "filelock"):
        fail("ADR-0006 anchor: no module under src/folio/ imports filelock")

    # ADR-0008: sample sheets under tests/fixtures/ must not bundle env state.
    fixtures_dir = ROOT / "tests" / "fixtures"
    if fixtures_dir.is_dir():
        forbidden = (".cache", ".venv", ".folio-cache", ".folio-runtime")
        for child in fixtures_dir.rglob("*"):
            if child.name in forbidden:
                fail(
                    f"{child.relative_to(ROOT)}: sample sheets must not bundle "
                    f"{child.name} per ADR-0008"
                )


def _any_module_imports(paths: list[Path], module: str) -> bool:
    pattern = re.compile(
        rf"^\s*(import\s+{re.escape(module)}\b|from\s+{re.escape(module)}\b)",
        re.MULTILINE,
    )
    for path in paths:
        if pattern.search(path.read_text(encoding="utf-8")):
            return True
    return False


def validate_release_python_publish_invariants() -> None:
    """Keep PyPI publishing tied to artifacts built in the same workflow run."""
    workflow_path = ROOT / ".github" / "workflows" / "release-python.yml"
    if not workflow_path.exists():
        return

    workflow = workflow_path.read_text(encoding="utf-8")
    build_and_release = _workflow_job_section(workflow, "build-and-release")
    publish_pypi = _workflow_job_section(workflow, "publish-pypi")
    if not publish_pypi:
        return

    if "gh release download" in publish_pypi:
        fail(
            ".github/workflows/release-python.yml: PyPI publishing must not "
            "download mutable GitHub Release assets"
        )

    for required_text in (
        "needs: build-and-release",
        "actions/download-artifact@",
        "packages-dir: dist",
    ):
        if required_text not in publish_pypi:
            fail(
                ".github/workflows/release-python.yml: publish-pypi must "
                f"include {required_text!r}"
            )

    skipped_release_condition = (
        "github.event_name == 'push' || github.event_name == 'workflow_dispatch'"
    )
    if skipped_release_condition in build_and_release:
        fail(
            ".github/workflows/release-python.yml: build-and-release must not "
            "skip release events used for PyPI publishing"
        )

    for run_snippet in _workflow_run_snippets(publish_pypi):
        if "github.event.release.tag_name" in run_snippet:
            fail(
                ".github/workflows/release-python.yml: release tag names must "
                "not be interpolated into publish-pypi shell commands"
            )


def _workflow_job_section(workflow: str, job_name: str) -> str:
    marker = f"  {job_name}:"
    if marker not in workflow:
        return ""
    tail = workflow.split(marker, 1)[1]
    next_job = re.search(r"\n  [A-Za-z0-9_-]+:\n", tail)
    if next_job:
        return tail[: next_job.start()]
    return tail


def _workflow_run_snippets(job_text: str) -> list[str]:
    snippets = [
        match.group(0)
        for match in re.finditer(r"(?m)^        run: [^\n]*", job_text)
    ]
    snippets.extend(
        match.group(0)
        for match in re.finditer(
            r"(?m)^        run:\s*[|>]\n(?:          .*\n?)+", job_text
        )
    )
    return snippets


def validate_desktop_agent_execution_invariants() -> None:
    """Keep portable sheets from influencing desktop agent executable lookup."""
    desktop_agents = ROOT / "apps" / "desktop" / "src" / "main" / "agents.ts"
    if not desktop_agents.exists():
        return

    text = desktop_agents.read_text(encoding="utf-8")
    for forbidden_text in (
        "env.PATH =",
        "process.env.PATH =",
        "env[\"PATH\"] =",
        "env['PATH'] =",
    ):
        if forbidden_text in text:
            fail(
                "apps/desktop/src/main/agents.ts: do not mutate PATH in "
                "runAgent; sheet-derived PATH entries can hijack agent binaries"
            )


def validate_desktop_agent_ipc_invariants() -> None:
    """Reject regressions where renderer IPC can choose agent cwd."""
    main_path = ROOT / "apps" / "desktop" / "src" / "main" / "main.ts"
    preload_path = ROOT / "apps" / "desktop" / "src" / "preload" / "preload.cjs"
    bridge_path = ROOT / "viewer" / "src" / "folio-bridge.d.ts"
    if not (main_path.exists() and preload_path.exists() and bridge_path.exists()):
        return

    main_text = main_path.read_text(encoding="utf-8")
    preload_text = preload_path.read_text(encoding="utf-8")
    bridge_text = bridge_path.read_text(encoding="utf-8")

    if "p.cwd" in main_text or "payload.cwd" in main_text:
        fail(
            "apps/desktop/src/main/main.ts: agents:run must ignore "
            "renderer-provided cwd"
        )

    if 'const cwd = currentSheet ?? "";' not in main_text:
        fail(
            "apps/desktop/src/main/main.ts: agents:run must derive cwd from "
            "currentSheet"
        )

    if 'run: (payload) => ipcRenderer.invoke("agents:run", payload)' in preload_text:
        fail(
            "apps/desktop/src/preload/preload.cjs: agents.run must not "
            "forward raw payloads"
        )

    if re.search(r"\bcwd\??\s*:", bridge_text):
        fail("viewer/src/folio-bridge.d.ts: AgentsBridge.run must not expose cwd")


validate_adr_anchored_invariants()
validate_release_python_publish_invariants()
validate_desktop_agent_execution_invariants()
validate_desktop_agent_ipc_invariants()
validate_failure_log((feature_list or {}).get("tasks") or [])


if errors:
    print("harness-drift: errors found", file=sys.stderr)
    for error in errors:
        print(f"  {error}", file=sys.stderr)
    sys.exit(1)

print("harness-drift: no deterministic drift detected")
