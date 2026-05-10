"""Tests for the Phase 4 ``http`` extension kind."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from folio import open_sheet
from folio.derivation import DerivationError, load_derivation
from folio.kinds import (
    HTTPDerivation,
    HTTPResponse,
    StubHTTPTransport,
    execute_http,
)


def _write_yaml(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return path


# --- Pydantic shape -------------------------------------------------------


def test_minimal_http_derivation_loads(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "weather.yaml",
        """
        targets: [temperature]
        inputs: [city]
        kind: http
        url: "https://api.example.com/{{ city }}"
        response_path: current.temp
        """,
    )
    derivation = load_derivation(path)
    assert isinstance(derivation, HTTPDerivation)
    assert derivation.method == "GET"


def test_http_multi_target_requires_response_schema(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "bad.yaml",
        """
        targets: [a, b]
        kind: http
        url: "https://api.example.com"
        """,
    )
    with pytest.raises(DerivationError, match="response_schema"):
        load_derivation(path)


def test_http_response_schema_keys_must_match_targets(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "bad.yaml",
        """
        targets: [a, b]
        kind: http
        url: "https://api.example.com"
        response_schema:
          a: data.a
          c: data.c
        """,
    )
    with pytest.raises(DerivationError, match="keys must equal targets"):
        load_derivation(path)


# --- Execution -----------------------------------------------------------


def test_execute_http_get_with_template_url() -> None:
    derivation = HTTPDerivation.model_validate(
        {
            "targets": ["temperature"],
            "inputs": ["city"],
            "kind": "http",
            "url": "https://api.example.com/weather/{{ city }}",
            "response_path": "current.temp",
        }
    )
    transport = StubHTTPTransport()
    transport.prepare(
        method="GET",
        url_substring="/weather/Tokyo",
        body='{"current": {"temp": 23}}',
        headers={"content-type": "application/json"},
    )

    values = execute_http(derivation, {"city": "Tokyo"}, transport=transport)

    assert values == {"temperature": 23}
    assert transport.calls[0]["method"] == "GET"
    assert transport.calls[0]["url"].endswith("/weather/Tokyo")


def test_execute_http_post_with_body_template() -> None:
    derivation = HTTPDerivation.model_validate(
        {
            "targets": ["sentiment"],
            "inputs": ["text"],
            "kind": "http",
            "url": "https://api.example.com/sentiment",
            "method": "POST",
            "headers": {"content-type": "application/json"},
            "body_template": '{"text": "{{ text }}"}',
            "response_path": "label",
        }
    )
    transport = StubHTTPTransport()
    transport.prepare(
        method="POST",
        url_substring="/sentiment",
        body='{"label": "positive"}',
        headers={"content-type": "application/json"},
    )

    values = execute_http(derivation, {"text": "great"}, transport=transport)

    assert values == {"sentiment": "positive"}
    assert transport.calls[0]["content"] == '{"text": "great"}'


def test_execute_http_multi_target_via_response_schema() -> None:
    derivation = HTTPDerivation.model_validate(
        {
            "targets": ["industry", "country"],
            "inputs": ["company"],
            "kind": "http",
            "url": "https://api.example.com/{{ company }}",
            "response_schema": {
                "industry": "info.industry",
                "country": "info.country",
            },
        }
    )
    transport = StubHTTPTransport()
    transport.prepare(
        method="GET",
        url_substring="/Acme",
        body='{"info": {"industry": "Manufacturing", "country": "Japan"}}',
        headers={"content-type": "application/json"},
    )

    values = execute_http(derivation, {"company": "Acme"}, transport=transport)
    assert values == {"industry": "Manufacturing", "country": "Japan"}


def test_execute_http_non_2xx_raises() -> None:
    derivation = HTTPDerivation.model_validate(
        {
            "targets": ["x"],
            "inputs": [],
            "kind": "http",
            "url": "https://api.example.com/x",
        }
    )
    transport = StubHTTPTransport()
    transport.prepare(method="GET", url_substring="/x", body="boom", status_code=500)

    from folio.exceptions import FolioError

    with pytest.raises(FolioError, match="status 500"):
        execute_http(derivation, {}, transport=transport)


def test_execute_http_missing_canned_response_raises() -> None:
    derivation = HTTPDerivation.model_validate(
        {
            "targets": ["x"],
            "inputs": [],
            "kind": "http",
            "url": "https://api.example.com/x",
        }
    )
    transport = StubHTTPTransport()
    from folio.exceptions import FolioError

    with pytest.raises(FolioError, match="no canned response"):
        execute_http(derivation, {}, transport=transport)


# --- Sheet.materialize integration ---------------------------------------


@pytest.fixture
def http_sheet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sheet = tmp_path / "sheet"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            """
            apiVersion: v3.0.0
            kind: DataContract
            id: http-test-{uid}
            name: http-test
            version: 1.0.0
            schema:
              - name: items
                physicalType: jsonl
                properties:
                  - name: id
                    logicalType: string
                    primaryKey: true
                    required: true
                  - name: city
                    logicalType: string
                    required: true
                  - name: temperature
                    logicalType: integer
                    x-derived: true
                    x-inputs: [city]
            """
        )
        .strip()
        .replace("{uid}", tmp_path.name),
        encoding="utf-8",
    )
    (sheet / "records.jsonl").write_text(
        '{"id": "r1", "city": "Tokyo"}\n'
        '{"id": "r2", "city": "Osaka"}\n',
        encoding="utf-8",
    )
    derivations = sheet / "derivations"
    derivations.mkdir()
    (derivations / "temperature.yaml").write_text(
        textwrap.dedent(
            """
            targets: [temperature]
            inputs: [city]
            kind: http
            url: "https://weather.example.com/{{ city }}"
            response_path: current.temp_c
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "folio._cache.default_cache_root",
        lambda sheet_id: tmp_path / "cache" / sheet_id,
    )
    return sheet


def test_materialize_http_populates_records(http_sheet: Path) -> None:
    sheet = open_sheet(http_sheet, actor="agent:test")
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

    result = sheet.materialize(http_transport=transport)
    assert result["materialized"] == 2
    assert result["failures"] == []

    rows = sheet.query("SELECT id, temperature FROM records ORDER BY id")
    assert rows == [
        {"id": "r1", "temperature": 23},
        {"id": "r2", "temperature": 26},
    ]


def test_materialize_http_without_transport_records_failures(http_sheet: Path) -> None:
    sheet = open_sheet(http_sheet, actor="agent:test")
    result = sheet.materialize()
    # No http_transport supplied, so each record × target becomes a failure.
    assert result["materialized"] == 0
    assert len(result["failures"]) == 2
    assert {entry["error_type"] for entry in result["failures"]} == {"OperationError"}
