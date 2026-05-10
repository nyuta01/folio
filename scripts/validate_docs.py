#!/usr/bin/env python3
"""Validate Folio design docs, ADR structure, and docs-local link integrity.

Run as `python3 scripts/validate_docs.py` from the repository root, or via
`make validate-docs`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN_ROOT = "docs/design-docs"
ADR_ROOT = f"{DESIGN_ROOT}/adrs"

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def exists(relative: str) -> bool:
    return (ROOT / relative).exists()


REQUIRED_FILES = [
    "design-doc.md",
    f"{DESIGN_ROOT}/README.md",
    f"{DESIGN_ROOT}/overview.md",
    f"{ADR_ROOT}/README.md",
    f"{ADR_ROOT}/template.md",
]

for relative in REQUIRED_FILES:
    if not exists(relative):
        fail(f"missing required docs file: {relative}")


if exists("design-doc.md"):
    pointer = read_text("design-doc.md")
    if "docs/design-docs/overview.md" not in pointer:
        fail("design-doc.md must point to docs/design-docs/overview.md")
    if len(pointer) > 1200:
        fail("design-doc.md must stay a short compatibility pointer (<= 1200 chars)")
    if re.search(r"^## ", pointer, re.MULTILINE):
        # A pointer should not contain its own structured sections.
        fail("design-doc.md must stay a short compatibility pointer (no `##` sections)")


if exists(f"{DESIGN_ROOT}/README.md"):
    index = read_text(f"{DESIGN_ROOT}/README.md")
    for link in ("overview.md", "adrs/README.md"):
        if link not in index:
            fail(f"{DESIGN_ROOT}/README.md must link {link}")


if exists(f"{DESIGN_ROOT}/overview.md"):
    overview = read_text(f"{DESIGN_ROOT}/overview.md")
    for required_text in (
        "Canonical path: `docs/design-docs/overview.md`",
        "Folio",
        "Phase 0",
    ):
        if required_text not in overview:
            fail(f"{DESIGN_ROOT}/overview.md must include {required_text}")


def section_body(text: str, heading: str) -> str:
    start = text.find(heading)
    if start == -1:
        return ""
    after_heading = text[start + len(heading):]
    next_heading = re.search(r"\n## ", after_heading)
    return after_heading if next_heading is None else after_heading[: next_heading.start()]


def validate_adr_file(relative_path: str, number: str) -> None:
    text = read_text(relative_path)
    if f"# ADR-{number} " not in text:
        fail(f"{relative_path}: H1 must start with # ADR-{number}")

    status_match = re.search(
        r"- \*\*Status\*\*: `?(proposed|accepted|rejected|deprecated|superseded)`?",
        text,
    )
    if not status_match:
        fail(f"{relative_path}: missing valid Status metadata")

    for heading in (
        "## Context",
        "## Decision",
        "## Consequences",
        "## Confirmation",
    ):
        if heading not in text:
            fail(f"{relative_path}: missing required ADR section {heading}")

    status = status_match.group(1) if status_match else None
    confirmation = section_body(text, "## Confirmation")
    if status == "accepted":
        if not confirmation.strip():
            fail(f"{relative_path}: accepted ADR must include confirmation text")
        elif not re.search(
            r"(make|pytest|test|smoke|verify|review|lint|check)",
            confirmation,
            re.IGNORECASE,
        ):
            fail(
                f"{relative_path}: accepted ADR confirmation must name a "
                "deterministic check or review path"
            )

    if status == "superseded" and not re.search(r"superseded by", text, re.IGNORECASE):
        fail(f"{relative_path}: superseded ADR must link the replacing ADR")


def validate_adrs() -> None:
    if not exists(ADR_ROOT):
        return

    index_path = f"{ADR_ROOT}/README.md"
    index = read_text(index_path) if exists(index_path) else ""

    files = sorted(
        entry.name
        for entry in (ROOT / ADR_ROOT).iterdir()
        if entry.suffix == ".md" and entry.name not in {"README.md", "template.md"}
    )

    if not files:
        fail(f"{ADR_ROOT}: must contain at least one ADR")
        return

    seen_numbers: set[str] = set()
    for index_position, file_name in enumerate(files):
        match = re.match(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$", file_name)
        if not match:
            fail(f"{ADR_ROOT}/{file_name}: ADR filename must match NNNN-kebab-title.md")
            continue

        number = match.group(1)
        if number in seen_numbers:
            fail(f"{ADR_ROOT}/{file_name}: duplicate ADR number {number}")
        seen_numbers.add(number)

        expected = str(index_position + 1).zfill(4)
        if number != expected:
            fail(
                f"{ADR_ROOT}/{file_name}: expected ADR number {expected}, "
                f"found {number}"
            )

        if file_name not in index:
            fail(f"{index_path}: missing link to {file_name}")

        validate_adr_file(f"{ADR_ROOT}/{file_name}", number)


def validate_local_markdown_links(paths: list[str]) -> None:
    for entry in paths:
        absolute = ROOT / entry
        if not absolute.exists():
            continue
        if absolute.is_dir():
            for child in absolute.iterdir():
                relative_child = str(child.relative_to(ROOT))
                validate_local_markdown_links([relative_child])
            continue
        if absolute.suffix != ".md":
            continue

        text = absolute.read_text(encoding="utf-8")
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
            raw_target = match.group(1).strip()
            if (
                raw_target == ""
                or raw_target.startswith("#")
                or raw_target.startswith("http://")
                or raw_target.startswith("https://")
                or raw_target.startswith("mailto:")
                or "://" in raw_target
            ):
                continue

            target_without_fragment = raw_target.split("#", 1)[0]
            if target_without_fragment == "":
                continue

            resolved = (absolute.parent / target_without_fragment).resolve()
            if resolved.exists() and resolved.is_dir():
                resolved = resolved / "README.md"

            if not resolved.exists():
                fail(f"{entry}: broken local link {raw_target}")


validate_adrs()
validate_local_markdown_links(["design-doc.md", DESIGN_ROOT])


if errors:
    print("validate-docs: errors found", file=sys.stderr)
    for error in errors:
        print(f"  {error}", file=sys.stderr)
    sys.exit(1)

print("validate-docs: ok")
