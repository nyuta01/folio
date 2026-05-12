#!/usr/bin/env python3
"""Verify SPECIFICATION.md against the reference implementation.

The spec at the repository root is the canonical document. This script
parses every `<!-- spec-table: <id> -->` block and asserts that the
table reflects the live code. Any drift fails CI; the spec — not the
code — is what must be updated.

Run from the repo root:

    python scripts/verify_spec.py

Exit code 0 ⇒ spec matches the implementation.
Exit code 1 ⇒ at least one drift; details printed to stderr.
"""

from __future__ import annotations

import inspect
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "SPECIFICATION.md"

# Make sure we import the in-repo source, not anything globally installed.
sys.path.insert(0, str(REPO_ROOT / "src"))


# ── Markdown parsing ────────────────────────────────────────────────────


def load_spec_text() -> str:
    if not SPEC_PATH.is_file():
        raise SystemExit(f"SPECIFICATION.md not found at {SPEC_PATH}")
    return SPEC_PATH.read_text(encoding="utf-8")


def extract_tables(text: str) -> dict[str, list[list[str]]]:
    """Return {table_id: rows} for every marked table.

    A "row" is a list of trimmed cell strings. The header row and the
    delimiter row are skipped; each data row is included verbatim so
    callers can inspect any column.
    """
    pattern = re.compile(
        r"<!--\s*spec-table:\s*(?P<id>[a-z0-9-]+)\s*-->\s*\n+"
        r"\|(?P<header>[^\n]+)\|\s*\n"
        r"\|(?P<sep>[^\n]+)\|\s*\n"
        r"(?P<body>(?:\|[^\n]+\|\s*\n)+)",
    )
    tables: dict[str, list[list[str]]] = {}
    for match in pattern.finditer(text):
        body = match.group("body")
        rows: list[list[str]] = []
        for line in body.strip().splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)
        tables[match.group("id")] = rows
    return tables


def first_column(rows: list[list[str]]) -> list[str]:
    """Return the first column (typically the field name), backtick-stripped."""
    out = []
    for row in rows:
        if not row:
            continue
        cell = row[0].strip()
        # Remove leading/trailing backticks to compare with bare names.
        m = re.match(r"^`([^`]+)`", cell)
        out.append(m.group(1) if m else cell)
    return out


# ── Result reporting ────────────────────────────────────────────────────


@dataclass
class CheckResult:
    name: str
    ok: bool = True
    missing: set[str] = field(default_factory=set)
    extra: set[str] = field(default_factory=set)
    detail: str | None = None

    def render(self) -> str:
        if self.ok:
            return f"  ok    {self.name}"
        lines = [f"  FAIL  {self.name}"]
        if self.missing:
            lines.append(f"        missing in spec: {sorted(self.missing)}")
        if self.extra:
            lines.append(f"        extra in spec:   {sorted(self.extra)}")
        if self.detail:
            lines.append(f"        {self.detail}")
        return "\n".join(lines)


def diff_sets(name: str, expected: set[str], spec_set: set[str]) -> CheckResult:
    res = CheckResult(name=name)
    res.missing = expected - spec_set
    res.extra = spec_set - expected
    res.ok = not res.missing and not res.extra
    return res


# ── Pydantic model checks ───────────────────────────────────────────────


def model_field_names(cls) -> set[str]:
    """Public field set keyed by alias (or attribute name) — i.e., the
    names that appear in the YAML the user writes."""
    return {f.alias or n for n, f in cls.model_fields.items()}


def check_contract_fields(spec_tables) -> list[CheckResult]:
    from folio.contract import Contract, Property, Schema

    return [
        diff_sets(
            "contract-fields",
            model_field_names(Contract),
            set(first_column(spec_tables.get("contract-fields", []))),
        ),
        diff_sets(
            "schema-fields",
            model_field_names(Schema),
            set(first_column(spec_tables.get("schema-fields", []))),
        ),
        diff_sets(
            "property-fields",
            model_field_names(Property),
            set(first_column(spec_tables.get("property-fields", []))),
        ),
    ]


def check_logical_types(spec_tables) -> list[CheckResult]:
    import typing

    from folio.contract import LogicalType

    expected = set(typing.get_args(LogicalType))
    spec = set(first_column(spec_tables.get("logical-types", [])))
    return [diff_sets("logical-types", expected, spec)]


def check_derivation_kinds(spec_tables) -> list[CheckResult]:
    from folio.derivation import _BaseDerivation, AIDerivation, ImportDerivation
    from folio.kinds._cross_sheet import CrossSheetDerivation
    from folio.kinds._http import HTTPDerivation
    from folio.kinds._python import PythonDerivation
    from folio.kinds._sql import SQLDerivation

    base = model_field_names(_BaseDerivation)
    # `kind` is the discriminator, declared per-subclass in code but
    # universal in the YAML — the spec lists it on the common shape.
    base_with_kind = base | {"kind"}

    pairs = [
        ("derivation-base-fields", base_with_kind),
        # Kind-specific tables list ONLY the per-kind extra fields plus
        # the discriminator. Compute the expected per-kind set as
        # (kind fields) − (base fields) ∪ {"kind"}, since `kind` is the
        # discriminator and the spec table includes it explicitly.
        (
            "derivation-ai-fields",
            (model_field_names(AIDerivation) - base) | {"kind"},
        ),
        (
            "derivation-import-fields",
            (model_field_names(ImportDerivation) - base) | {"kind"},
        ),
        (
            "derivation-python-fields",
            (model_field_names(PythonDerivation) - base) | {"kind"},
        ),
        (
            "derivation-sql-fields",
            (model_field_names(SQLDerivation) - base) | {"kind"},
        ),
        (
            "derivation-http-fields",
            (model_field_names(HTTPDerivation) - base) | {"kind"},
        ),
        (
            "derivation-cross-sheet-fields",
            (model_field_names(CrossSheetDerivation) - base) | {"kind"},
        ),
    ]
    return [
        diff_sets(name, expected, set(first_column(spec_tables.get(name, []))))
        for name, expected in pairs
    ]


def check_provenance_source(spec_tables) -> list[CheckResult]:
    expected = {"ai", "import", "python", "sql", "http", "cross_sheet", "human_override"}
    spec = set(first_column(spec_tables.get("provenance-source", [])))
    return [diff_sets("provenance-source", expected, spec)]


def check_provenance_fields(spec_tables) -> list[CheckResult]:
    # Hand-curated set: the keys that Sheet.materialize ever writes plus
    # the optional ones documented in §3.3.1.
    expected = {
        "record_id",
        "field",
        "source",
        "actor",
        "at",
        "input_hash",
        "model",
        "cost_usd",
    }
    spec = set(first_column(spec_tables.get("provenance-fields", [])))
    return [diff_sets("provenance-fields", expected, spec)]


def check_readme_frontmatter(spec_tables) -> list[CheckResult]:
    from folio.readme import Frontmatter

    expected = model_field_names(Frontmatter)
    spec = set(first_column(spec_tables.get("readme-frontmatter", [])))
    return [diff_sets("readme-frontmatter", expected, spec)]


# ── Surfaces ────────────────────────────────────────────────────────────


def check_cli_verbs(spec_tables) -> list[CheckResult]:
    from folio.cli import app

    expected: set[str] = set()
    for cmd in app.registered_commands:
        expected.add(cmd.name or cmd.callback.__name__)
    # add registered_groups (sub-apps): script, export
    for group in app.registered_groups:
        expected.add(group.name)

    spec = set(first_column(spec_tables.get("cli-verbs", [])))
    return [diff_sets("cli-verbs", expected, spec)]


def check_sdk_methods(spec_tables) -> list[CheckResult]:
    from folio.sheet import Sheet

    expected = {
        name
        for name, _ in inspect.getmembers(Sheet, inspect.isfunction)
        if not name.startswith("_")
    }
    spec = set(first_column(spec_tables.get("sdk-methods", [])))
    return [diff_sets("sdk-methods", expected, spec)]


def check_viewer_routes(spec_tables) -> list[CheckResult]:
    from folio_viewer.server import build_app

    sheet_path = REPO_ROOT / "examples" / "customers"
    if not sheet_path.is_dir():
        return [
            CheckResult(
                name="viewer-routes",
                ok=False,
                detail=f"fixture sheet missing at {sheet_path}",
            )
        ]
    api = build_app(sheet_path=sheet_path)
    expected: set[str] = set()
    for route in api.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", set()) or set()
        if not path:
            continue
        if not (path.startswith("/api/") or path == "/events"):
            continue
        for method in sorted(methods - {"HEAD"}):
            expected.add(f"{method} {path}")

    spec_rows = spec_tables.get("viewer-routes", [])
    spec_set: set[str] = set()
    for row in spec_rows:
        if len(row) < 2:
            continue
        method = row[0].strip()
        path = row[1].strip().strip("`")
        spec_set.add(f"{method} {path}")
    return [diff_sets("viewer-routes", expected, spec_set)]


def check_exceptions(spec_tables) -> list[CheckResult]:
    import folio.derivation as _derivation
    import folio.exceptions as _exceptions

    expected = {
        name
        for name, obj in inspect.getmembers(_exceptions, inspect.isclass)
        if name.endswith("Error") and obj.__module__ == _exceptions.__name__
    }
    expected.add("DerivationError")  # lives in folio.derivation, not exceptions
    # Sanity: it should actually exist
    assert hasattr(_derivation, "DerivationError")
    spec = set(first_column(spec_tables.get("exceptions", [])))
    return [diff_sets("exceptions", expected, spec)]


# ── Driver ──────────────────────────────────────────────────────────────


def main() -> int:
    text = load_spec_text()
    spec_tables = extract_tables(text)

    results: list[CheckResult] = []
    for fn in (
        check_contract_fields,
        check_logical_types,
        check_derivation_kinds,
        check_provenance_source,
        check_provenance_fields,
        check_readme_frontmatter,
        check_cli_verbs,
        check_sdk_methods,
        check_viewer_routes,
        check_exceptions,
    ):
        try:
            results.extend(fn(spec_tables))
        except Exception as err:  # noqa: BLE001  (driver should never crash)
            results.append(
                CheckResult(
                    name=fn.__name__,
                    ok=False,
                    detail=f"check raised: {err!r}",
                )
            )

    failed = [r for r in results if not r.ok]
    print("verify_spec — SPECIFICATION.md ↔ reference implementation")
    for r in results:
        print(r.render())
    if failed:
        print(f"\n{len(failed)} drift(s) found. Update SPECIFICATION.md.")
        return 1
    print(f"\nall {len(results)} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
