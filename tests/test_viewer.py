"""Tests for ``folio_viewer.server`` (Phase 5 V0–V3).

The FastAPI app is exercised in-process via Starlette's ``TestClient``
so no real socket is opened. The companion ``scripts/smoke-viewer.sh``
covers the live ``uvicorn`` round-trip.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from folio._ai_kind import StubAIClient
from folio_viewer.server import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, build_app


@pytest.fixture
def viewer_sheet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sheet = tmp_path / "customers"
    sheet.mkdir()
    (sheet / "contract.yaml").write_text(
        textwrap.dedent(
            """
            apiVersion: v3.0.0
            kind: DataContract
            id: viewer-customers-{uid}
            name: viewer-customers
            version: 1.0.0
            schema:
              - name: items
                physicalType: jsonl
                properties:
                  - name: id
                    logicalType: string
                    primaryKey: true
                    required: true
                  - name: company_name
                    logicalType: string
                    required: true
                    x-editable-by: ["agent:human", "agent:test"]
                  - name: industry_tag
                    logicalType: string
                    x-derived: true
                    x-inputs: [company_name]
            """
        )
        .strip()
        .replace("{uid}", tmp_path.name),
        encoding="utf-8",
    )
    (sheet / "records.jsonl").write_text(
        '{"id": "cust_001", "company_name": "Acme"}\n'
        '{"id": "cust_002", "company_name": "DataFlow"}\n',
        encoding="utf-8",
    )
    derivations = sheet / "derivations"
    derivations.mkdir()
    (derivations / "industry_tag.yaml").write_text(
        textwrap.dedent(
            """
            targets: [industry_tag]
            inputs: [company_name]
            kind: ai
            model: claude-sonnet-4-6
            prompt: |
              Industry of {{ company_name }} in one word.
            output: text
            """
        ).strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "folio._cache.default_cache_root",
        lambda sheet_id: tmp_path / "cache" / sheet_id,
    )
    return sheet


def _client(app) -> TestClient:
    return TestClient(app, base_url="http://testserver")


@pytest.fixture
def viewer_client(viewer_sheet: Path) -> Iterator[TestClient]:
    stub = StubAIClient()
    stub.prepare("Industry of Acme", "Manufacturing")
    stub.prepare("Industry of DataFlow", "Software")
    app = build_app(
        sheet_path=viewer_sheet,
        default_actor="agent:test",
        ai_client=stub,
    )
    with _client(app) as client:
        yield client


def _csrf(client: TestClient) -> str:
    response = client.get("/api/csrf")
    assert response.status_code == 200
    token = response.json()["csrf_token"]
    assert client.cookies.get(CSRF_COOKIE_NAME) == token
    return token


# --- V0 / V1 read routes ---------------------------------------------------


def test_get_contract_returns_dump(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/contract")
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "DataContract"
    assert body["schema"][0]["name"] == "items"


def test_list_records_returns_envelope(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/records", params={"fields": "id,company_name"})
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "json"
    assert {row["id"] for row in body["records"]} == {"cust_001", "cust_002"}


def test_get_record_returns_single(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/records/cust_001")
    assert response.status_code == 200
    assert response.json()["company_name"] == "Acme"


def test_get_record_404(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/records/missing")
    assert response.status_code == 404


def test_query_returns_rows(viewer_client: TestClient) -> None:
    _csrf(viewer_client)
    response = viewer_client.post(
        "/api/query",
        json={"sql": "SELECT id FROM records ORDER BY id"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["rows"] == [{"id": "cust_001"}, {"id": "cust_002"}]


def test_query_rejects_non_select(viewer_client: TestClient) -> None:
    response = viewer_client.post(
        "/api/query",
        json={"sql": "DELETE FROM records"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "QueryError"


def test_query_rejects_stacked_statement(viewer_client: TestClient) -> None:
    response = viewer_client.post(
        "/api/query",
        json={"sql": "SELECT id FROM records; SELECT company_name FROM records"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "QueryError"


def test_query_sandbox_blocks_external_file_reads(
    viewer_client: TestClient, tmp_path: Path
) -> None:
    secret = tmp_path / "secret.csv"
    secret.write_text("line\nFOLIO_SECRET_FILE_READ_TOKEN_12345\n", encoding="utf-8")

    response = viewer_client.post(
        "/api/query",
        json={"sql": f"SELECT line FROM read_csv('{secret}')"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "QueryError"
    assert "FOLIO_SECRET_FILE_READ_TOKEN_12345" not in response.text


# --- V2 mutating routes (CSRF) --------------------------------------------


def test_upsert_records_requires_csrf(viewer_client: TestClient) -> None:
    response = viewer_client.post(
        "/api/records",
        json={"records": [{"id": "cust_003", "company_name": "Green Farm"}]},
    )
    assert response.status_code == 403


def test_upsert_records_round_trip(viewer_client: TestClient) -> None:
    token = _csrf(viewer_client)
    response = viewer_client.post(
        "/api/records",
        json={"records": [{"id": "cust_003", "company_name": "Green Farm"}]},
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["inserted"] == 1
    assert body["total"] == 3


def test_delete_records_requires_csrf(viewer_client: TestClient) -> None:
    response = viewer_client.delete("/api/records", params={"ids": "cust_001"})
    assert response.status_code == 403


def test_delete_records_with_csrf(viewer_client: TestClient) -> None:
    token = _csrf(viewer_client)
    response = viewer_client.delete(
        "/api/records",
        params={"ids": "cust_001"},
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 200
    assert response.json()["deleted"] == 1


def test_csrf_mismatch_rejected(viewer_client: TestClient) -> None:
    _csrf(viewer_client)
    response = viewer_client.post(
        "/api/records",
        json={"records": [{"id": "cust_004", "company_name": "Other"}]},
        headers={CSRF_HEADER_NAME: "wrong-token"},
    )
    assert response.status_code == 403


def test_editable_by_violation_403(viewer_client: TestClient, viewer_sheet: Path) -> None:
    """Actor not in ``x-editable-by`` is rejected as 403 (PermissionDeniedError)."""
    stub = StubAIClient()
    app = build_app(
        sheet_path=viewer_sheet,
        default_actor="agent:not-allowed",
        ai_client=stub,
    )
    with _client(app) as client:
        token = _csrf(client)
        response = client.post(
            "/api/records",
            json={
                "records": [
                    {"id": "cust_001", "company_name": "Renamed"}
                ]
            },
            headers={CSRF_HEADER_NAME: token},
        )
        assert response.status_code == 403
        assert response.json()["error"]["type"] == "PermissionDeniedError"


# --- V3 materialize + provenance ------------------------------------------


def test_status_returns_per_target(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert "industry_tag" in body


def test_materialize_uses_injected_stub(viewer_client: TestClient) -> None:
    token = _csrf(viewer_client)
    response = viewer_client.post(
        "/api/materialize",
        json={},
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["materialized"] == 2
    assert body["failures"] == []


def test_provenance_after_materialize(viewer_client: TestClient) -> None:
    token = _csrf(viewer_client)
    viewer_client.post("/api/materialize", json={}, headers={CSRF_HEADER_NAME: token})
    response = viewer_client.get(
        "/api/provenance",
        params={"record_id": "cust_001", "field": "industry_tag"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ai"


# --- safety guards --------------------------------------------------------


def test_build_app_rejects_missing_sheet(tmp_path: Path) -> None:
    from folio.exceptions import SheetError

    with pytest.raises(SheetError, match="not a directory"):
        build_app(sheet_path=tmp_path / "missing")


def test_static_dir_mounts_when_present(tmp_path: Path, viewer_sheet: Path) -> None:
    static_dir = tmp_path / "frontend"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        "<!doctype html><title>folio</title>", encoding="utf-8"
    )
    app = build_app(sheet_path=viewer_sheet, static_dir=static_dir)
    with _client(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert b"folio" in response.content


# --- Contract editing -----------------------------------------------------


def test_add_property_appends(viewer_client: TestClient) -> None:
    token = _csrf(viewer_client)
    response = viewer_client.post(
        "/api/contract/properties",
        json={"name": "tagline", "logicalType": "string", "editable_by": ["agent:test"]},
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 200
    contract = response.json()
    names = [p["name"] for p in contract["schema"][0]["properties"]]
    assert names[-1] == "tagline"


def test_add_property_rejects_duplicate(viewer_client: TestClient) -> None:
    token = _csrf(viewer_client)
    response = viewer_client.post(
        "/api/contract/properties",
        json={"name": "company_name", "logicalType": "string"},
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "OperationError"


def test_update_property_renames_and_migrates_records(viewer_client: TestClient) -> None:
    token = _csrf(viewer_client)
    viewer_client.post(
        "/api/contract/properties",
        json={"name": "tagline", "logicalType": "string", "editable_by": ["agent:test"]},
        headers={CSRF_HEADER_NAME: token},
    )
    viewer_client.post(
        "/api/records",
        json={
            "records": [{"id": "cust_001", "tagline": "We make things"}],
            "actor": "agent:test",
        },
        headers={CSRF_HEADER_NAME: token},
    )
    response = viewer_client.patch(
        "/api/contract/properties/tagline",
        json={"new_name": "slogan"},
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 200
    contract = response.json()
    names = [p["name"] for p in contract["schema"][0]["properties"]]
    assert "slogan" in names
    assert "tagline" not in names

    listing = viewer_client.get("/api/records").json()
    one = next(r for r in listing["records"] if r["id"] == "cust_001")
    assert "slogan" in one
    assert "tagline" not in one


def test_update_property_rejects_rename_when_referenced(
    viewer_client: TestClient,
) -> None:
    token = _csrf(viewer_client)
    response = viewer_client.patch(
        "/api/contract/properties/company_name",
        json={"new_name": "company_legal_name"},
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 400
    assert "x-inputs" in response.json()["error"]["message"]


def test_update_property_rejects_pk(viewer_client: TestClient) -> None:
    token = _csrf(viewer_client)
    response = viewer_client.patch(
        "/api/contract/properties/id",
        json={"description": "new desc"},
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 400
    assert "primary-key" in response.json()["error"]["message"]


def test_delete_property_strips_records(viewer_client: TestClient) -> None:
    token = _csrf(viewer_client)
    # first add a non-derived field to delete
    viewer_client.post(
        "/api/contract/properties",
        json={"name": "tagline", "logicalType": "string", "editable_by": ["agent:test"]},
        headers={CSRF_HEADER_NAME: token},
    )
    response = viewer_client.delete(
        "/api/contract/properties/tagline",
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 200
    contract = response.json()
    names = [p["name"] for p in contract["schema"][0]["properties"]]
    assert "tagline" not in names


def test_delete_property_refuses_derived(viewer_client: TestClient) -> None:
    token = _csrf(viewer_client)
    response = viewer_client.delete(
        "/api/contract/properties/industry_tag",
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 400
    assert "derived" in response.json()["error"]["message"]
