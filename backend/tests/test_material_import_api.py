import io

import pytest


def test_import_materials_csv_endpoint(client, auth_headers):
    csv_content = (
        "item_number,description,unit_price,uom,category,source,ocr_flag\n"
        "ABC123,Test Shingle,117.96,SQ,Shingles,ABC Roofing,\n"
        "DEF456,Test Nail,9.50,BX,Fasteners,ABC Roofing,\n"
    )
    resp = client.post(
        "/api/materials/import",
        headers=auth_headers,
        files={"file": ("materials.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["materials_imported"] == 2
    assert data["price_lists_created"] == 1
    assert data["errors"] == []


def test_import_materials_no_file(client, auth_headers):
    resp = client.post("/api/materials/import", headers=auth_headers)
    assert resp.status_code == 422


def test_import_requires_auth(client):
    resp = client.post("/api/materials/import")
    assert resp.status_code == 401
