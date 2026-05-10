#!/usr/bin/env python3
"""Validate Folio repository harness shape and structured task state.

Run as `python3 scripts/harness_check.py` from the repository root, or via
`make harness-check`.
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


REQUIRED_FILES = [
    "AGENTS.md",
    "AGENT_PROGRESS.md",
    "Makefile",
    "README.md",
    "pyproject.toml",
    ".github/workflows/verify.yml",
    "design-doc.md",
    "docs/design-docs/README.md",
    "docs/design-docs/overview.md",
    "docs/design-docs/adrs/README.md",
    "docs/design-docs/adrs/template.md",
    "docs/QUALITY_SCORE.md",
    "docs/agent-failures.md",
    "docs/methodology/harness-engineering.md",
    "docs/methodology/permanent-fix-protocol.md",
    "docs/methodology/self-pdca-loop.md",
    "docs/exec-plans/README.md",
    "docs/exec-plans/active/README.md",
    "docs/exec-plans/feature-list.json",
    "docs/product-specs/README.md",
    "docs/product-specs/phase-0-minimum-sheet.md",
    "scripts/agent-init.sh",
    "scripts/harness_check.py",
    "scripts/harness_drift.py",
    "scripts/validate_docs.py",
    "src/folio/__init__.py",
    "src/folio/cli.py",
    "src/folio/contract.py",
    "src/folio/derivation.py",
    "src/folio/exceptions.py",
    "src/folio/sheet.py",
    "src/folio/_records.py",
    "src/folio/_lock.py",
    "src/folio/_query.py",
    "src/folio/_import_kind.py",
    "src/folio/_cache.py",
    "src/folio/_provenance.py",
    "src/folio/_ai_kind.py",
    "src/folio/scripts.py",
    "src/folio/readme.py",
    "src/folio/_toon.py",
    "src/folio_mcp/__init__.py",
    "src/folio_mcp/server.py",
    "src/folio_mcp/cli.py",
    "src/folio_viewer/__init__.py",
    "src/folio_viewer/server.py",
    "src/folio_viewer/cli.py",
    "src/folio_viewer/_events.py",
    "src/folio/kinds/__init__.py",
    "src/folio/kinds/_sql.py",
    "src/folio/kinds/_http.py",
    "src/folio/kinds/_python.py",
    "src/folio/kinds/_cross_sheet.py",
    "src/folio/datapackage.py",
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/test_contract.py",
    "tests/test_sheet.py",
    "tests/test_cli.py",
    "tests/test_derivation.py",
    "tests/test_import_kind.py",
    "tests/test_cache.py",
    "tests/test_provenance.py",
    "tests/test_ai_kind.py",
    "tests/test_materialize.py",
    "tests/test_scripts.py",
    "tests/test_readme.py",
    "tests/test_toon.py",
    "tests/test_mcp.py",
    "tests/test_kind_sql.py",
    "tests/test_kind_http.py",
    "tests/test_kind_python.py",
    "tests/test_kind_cross_sheet.py",
    "tests/test_datapackage.py",
    "tests/test_viewer.py",
    "tests/test_viewer_events.py",
    "tests/fixtures/import-kind/customers.csv",
    "tests/fixtures/import-kind/legacy.jsonl",
    "viewer/package.json",
    "viewer/index.html",
    "viewer/src/main.tsx",
    "viewer/src/App.tsx",
    "viewer/src/api.ts",
    "viewer/src/types.ts",
    "viewer/src/Icons.tsx",
    "viewer/src/QueryBar.tsx",
    "viewer/src/RightPanel.tsx",
    "viewer/src/RecordsGrid.tsx",
    "viewer/src/useEventStream.ts",
    "viewer/src/index.css",
    "viewer/playwright.config.ts",
    "viewer/tests/grid.spec.ts",
    "scripts/smoke-cli.sh",
    "scripts/smoke-materialize.sh",
    "scripts/_materialize_smoke.py",
    "scripts/smoke-scripts.sh",
    "scripts/smoke-mcp.sh",
    "scripts/_mcp_smoke.py",
    "scripts/smoke-extension-kinds.sh",
    "scripts/_extension_kinds_smoke.py",
    "scripts/smoke-viewer.sh",
    "scripts/_viewer_smoke.py",
]

for relative in REQUIRED_FILES:
    if not exists(relative):
        fail(f"missing required harness file: {relative}")

if exists("AGENTS.md"):
    line_count = len(read_text("AGENTS.md").rstrip("\n").split("\n"))
    if line_count > 120:
        fail(f"AGENTS.md must stay compact; found {line_count} lines, max 120")


feature_list: dict | None = None
if exists("docs/exec-plans/feature-list.json"):
    try:
        feature_list = json.loads(read_text("docs/exec-plans/feature-list.json"))
    except json.JSONDecodeError as exc:
        fail(f"feature-list.json is not valid JSON: {exc}")


def validate_tasks(tasks: list[dict]) -> None:
    seen_ids: set[str] = set()
    allowed_statuses = {"todo", "in_progress", "blocked", "done"}
    allowed_priorities = {"P0", "P1", "P2"}

    for task in tasks:
        prefix = task.get("id", "<missing-id>")

        for field in ("id", "title", "priority", "status", "owner"):
            value = task.get(field)
            if not isinstance(value, str) or not value:
                fail(f"{prefix}: missing string field {field}")

        task_id = task.get("id")
        if isinstance(task_id, str):
            if task_id in seen_ids:
                fail(f"{prefix}: duplicate task id")
            seen_ids.add(task_id)

        if task.get("priority") not in allowed_priorities:
            fail(f"{prefix}: invalid priority {task.get('priority')!r}")

        if task.get("status") not in allowed_statuses:
            fail(f"{prefix}: invalid status {task.get('status')!r}")

        if not isinstance(task.get("depends"), list):
            fail(f"{prefix}: depends must be an array")

        plan_url = task.get("plan_url")
        if plan_url is not None and (not isinstance(plan_url, str) or not plan_url):
            fail(f"{prefix}: plan_url must be a string or null when present")
        if isinstance(plan_url, str) and not exists(plan_url):
            fail(f"{prefix}: plan_url references missing file {plan_url}")

        if task.get("status") == "done" and not plan_url:
            fail(f"{prefix}: done tasks must link an active plan")

        paths = task.get("paths")
        if not isinstance(paths, list):
            fail(f"{prefix}: paths must be an array")
        elif task.get("status") == "done":
            for task_path in paths:
                if not exists(task_path):
                    fail(f"{prefix}: done task references missing path {task_path}")

        verification = task.get("verification")
        if not isinstance(verification, dict):
            fail(f"{prefix}: verification must be an object")
        elif task.get("status") == "done":
            for gate, value in verification.items():
                if value is False and not task.get("verification_override_reason"):
                    fail(f"{prefix}: done task has false verification gate {gate}")


if feature_list is not None:
    if feature_list.get("schema_version") != 1:
        fail("feature-list.json schema_version must be 1")
    tasks = feature_list.get("tasks")
    if not isinstance(tasks, list):
        fail("feature-list.json tasks must be an array")
    else:
        validate_tasks(tasks)


if exists("docs/design-docs/overview.md"):
    overview = read_text("docs/design-docs/overview.md")
    if "Canonical path: `docs/design-docs/overview.md`" not in overview:
        fail("docs/design-docs/overview.md must declare its canonical path")
    if "Folio" not in overview:
        fail("docs/design-docs/overview.md must reference the project name Folio")


if exists("docs/design-docs/README.md"):
    design_index = read_text("docs/design-docs/README.md")
    for link in ("overview.md", "adrs/README.md"):
        if link not in design_index:
            fail(f"docs/design-docs/README.md must link {link}")


if exists("docs/methodology/self-pdca-loop.md"):
    pdca = read_text("docs/methodology/self-pdca-loop.md")
    for phase in ("Plan", "Do", "Check", "Act"):
        if phase not in pdca:
            fail(f"self-pdca-loop.md must describe the {phase} phase")


if exists("docs/QUALITY_SCORE.md"):
    quality = read_text("docs/QUALITY_SCORE.md")
    for domain in ("Harness PDCA", "Sheet Spec", "Phase 0 SDK"):
        if domain not in quality:
            fail(f"QUALITY_SCORE.md must track {domain}")


if exists("Makefile"):
    makefile = read_text("Makefile")
    for target_fragment in (
        r"^verify:.*harness-check",
        r"^verify:.*drift-check",
        r"^verify:.*validate-docs",
        r"^verify:.*python-test",
        r"^verify:.*cli-smoke",
        r"^verify:.*materialize-smoke",
        r"^verify:.*scripts-smoke",
        r"^verify:.*mcp-smoke",
        r"^verify:.*extension-kinds-smoke",
        r"^verify:.*viewer-smoke",
    ):
        if not re.search(target_fragment, makefile, re.MULTILINE):
            fail(f"Makefile verify target must match {target_fragment}")


if exists(".github/workflows/verify.yml"):
    workflow = read_text(".github/workflows/verify.yml")
    if "pull_request:" not in workflow:
        fail(".github/workflows/verify.yml must run on pull_request")
    if "branches:" not in workflow:
        fail(".github/workflows/verify.yml must constrain push branches")
    for required_text in (
        "actions/setup-python@",
        "astral-sh/setup-uv@",
        "uv sync",
        "make verify",
    ):
        if required_text not in workflow:
            fail(f".github/workflows/verify.yml must include {required_text}")


if errors:
    print("harness-check: errors found", file=sys.stderr)
    for error in errors:
        print(f"  {error}", file=sys.stderr)
    sys.exit(1)

print("harness-check: ok")
