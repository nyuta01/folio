"""Deterministic offline smoke for Phase 4 sql + http extension kinds."""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest.mock as mock
from pathlib import Path
from typing import Any

import folio
from folio.kinds import StubHTTPTransport


CONTRACT = textwrap.dedent(
    """
    apiVersion: v3.0.0
    kind: DataContract
    id: ext-smoke
    name: ext-smoke
    version: 1.0.0
    schema:
      - name: items
        physicalType: jsonl
        properties:
          - name: id
            logicalType: string
            primaryKey: true
            required: true
          - name: amount
            logicalType: integer
          - name: city
            logicalType: string
          - name: total
            logicalType: integer
            x-derived: true
          - name: temperature
            logicalType: integer
            x-derived: true
            x-inputs: [city]
    """
).strip()


SQL_DERIVATION = textwrap.dedent(
    """
    targets: [total]
    inputs: []
    kind: sql
    expression: "SELECT SUM(amount) AS total FROM records"
    """
).strip()


HTTP_DERIVATION = textwrap.dedent(
    """
    targets: [temperature]
    inputs: [city]
    kind: http
    url: "https://weather.example.com/{{ city }}"
    response_path: current.temp_c
    """
).strip()


RECORDS = (
    '{"id": "a", "amount": 10, "city": "Tokyo"}\n'
    '{"id": "b", "amount": 20, "city": "Osaka"}\n'
)


def _expect(label: str, expected: Any, actual: Any) -> None:
    if expected != actual:
        raise AssertionError(
            f"smoke-extension-kinds: {label} expected {expected!r}, got {actual!r}"
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="folio-ext-smoke-") as tmp:
        root = Path(tmp)
        sheet = root / "ext"
        sheet.mkdir()
        (sheet / "contract.yaml").write_text(CONTRACT, encoding="utf-8")
        (sheet / "records.jsonl").write_text(RECORDS, encoding="utf-8")
        derivations = sheet / "derivations"
        derivations.mkdir()
        (derivations / "total.yaml").write_text(SQL_DERIVATION, encoding="utf-8")
        (derivations / "temperature.yaml").write_text(HTTP_DERIVATION, encoding="utf-8")

        cache_dir = root / "cache"

        with mock.patch(
            "folio._cache.default_cache_root",
            lambda sheet_id: cache_dir / sheet_id,
        ):
            transport = StubHTTPTransport()
            transport.prepare(
                method="GET",
                url_substring="/Tokyo",
                body='{"current": {"temp_c": 23}}',
                headers={"content-type": "application/json"},
            )
            transport.prepare(
                method="GET",
                url_substring="/Osaka",
                body='{"current": {"temp_c": 26}}',
                headers={"content-type": "application/json"},
            )

            s = folio.open_sheet(sheet, actor="agent:smoke")
            result = s.materialize(http_transport=transport)
            if result["failures"]:
                raise AssertionError(
                    f"smoke-extension-kinds: unexpected failures: {result['failures']}"
                )
            _expect("materialized count", 4, result["materialized"])

            rows = s.query(
                "SELECT id, total, temperature FROM records ORDER BY id"
            )
            _expect("Tokyo total", 30, rows[0]["total"])
            _expect("Tokyo temperature", 23, rows[0]["temperature"])
            _expect("Osaka temperature", 26, rows[1]["temperature"])

    print("smoke-extension-kinds: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
