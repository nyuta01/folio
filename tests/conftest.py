"""Shared fixtures for Folio tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

MINIMAL_CONTRACT = textwrap.dedent(
    """
    apiVersion: v3.0.0
    kind: DataContract
    id: test
    name: test
    version: 1.0.0
    schema:
      - name: items
        physicalType: jsonl
        properties:
          - name: id
            logicalType: string
            primaryKey: true
            required: true
          - name: title
            logicalType: string
            required: true
          - name: count
            logicalType: integer
    """
).strip()


@pytest.fixture
def minimal_sheet(tmp_path: Path) -> Path:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(MINIMAL_CONTRACT, encoding="utf-8")
    (sheet / "records.jsonl").write_text("", encoding="utf-8")
    return sheet


@pytest.fixture
def populated_sheet(minimal_sheet: Path) -> Path:
    body = (
        '{"id": "a", "title": "Alpha", "count": 1}\n'
        '{"id": "b", "title": "Beta", "count": 2}\n'
        '{"id": "c", "title": "Gamma", "count": 3}\n'
    )
    (minimal_sheet / "records.jsonl").write_text(body, encoding="utf-8")
    return minimal_sheet
