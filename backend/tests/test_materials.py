from decimal import Decimal

import pytest

from app.models.material import Material
from app.models.price_list import PriceList


@pytest.fixture()
def price_list(db_session):
    pl = PriceList(name="ABC Roofing", source_file="test.csv")
    db_session.add(pl)
    db_session.commit()
    db_session.refresh(pl)
    return pl


@pytest.fixture()
def sample_materials(db_session, price_list):
    materials = [
        Material(
            price_list_id=price_list.id,
            item_number="ABC001",
            description="OC Duration Brownwood",
            unit_price=Decimal("117.96"),
            uom="SQ",
            category="Shingles",
        ),
        Material(
            price_list_id=price_list.id,
            item_number="ABC002",
            description="Coil Nail 1.25 inch",
            unit_price=Decimal("45.00"),
            uom="BX",
            category="Fasteners",
        ),
        Material(
            price_list_id=price_list.id,
            item_number="ABC003",
            description="OC Starter Strip",
            unit_price=Decimal("47.21"),
            uom="BD",
            category="Starter Strip",
            ocr_flag="REVIEW - price may have OCR error",
        ),
    ]
    db_session.add_all(materials)
    db_session.commit()
    return materials


def test_list_materials(client, auth_headers, price_list, sample_materials):
    resp = client.get("/api/materials", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_list_materials_search(client, auth_headers, price_list, sample_materials):
    resp = client.get(
        "/api/materials", headers=auth_headers, params={"search": "Duration"}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["item_number"] == "ABC001"


def test_list_materials_filter_category(client, auth_headers, price_list, sample_materials):
    resp = client.get(
        "/api/materials", headers=auth_headers, params={"category": "Fasteners"}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_list_materials_filter_price_list(client, auth_headers, price_list, sample_materials):
    resp = client.get(
        "/api/materials",
        headers=auth_headers,
        params={"price_list_id": price_list.id},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


def test_list_materials_filter_flagged(client, auth_headers, price_list, sample_materials):
    resp = client.get(
        "/api/materials", headers=auth_headers, params={"flagged": "true"}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["item_number"] == "ABC003"


def test_list_materials_pagination(client, auth_headers, price_list, sample_materials):
    resp = client.get(
        "/api/materials", headers=auth_headers, params={"per_page": 2, "page": 1}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1


def test_get_material(client, auth_headers, price_list, sample_materials):
    mat_id = sample_materials[0].id
    resp = client.get(f"/api/materials/{mat_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["item_number"] == "ABC001"
    assert data["price_list_name"] == "ABC Roofing"


def test_get_material_not_found(client, auth_headers):
    resp = client.get("/api/materials/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_create_material(client, auth_headers, price_list):
    resp = client.post(
        "/api/materials",
        headers=auth_headers,
        json={
            "price_list_id": price_list.id,
            "item_number": "NEW001",
            "description": "New Test Item",
            "unit_price": "25.50",
            "uom": "PC",
            "category": "Fasteners",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["item_number"] == "NEW001"
    assert data["unit_price"] == "25.50"


def test_update_material(client, auth_headers, price_list, sample_materials):
    mat_id = sample_materials[0].id
    resp = client.put(
        f"/api/materials/{mat_id}",
        headers=auth_headers,
        json={"unit_price": "125.00", "ocr_flag": None},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_price"] == "125.00"


def test_update_material_clear_ocr_flag(client, auth_headers, price_list, sample_materials):
    mat_id = sample_materials[2].id
    resp = client.put(
        f"/api/materials/{mat_id}",
        headers=auth_headers,
        json={"ocr_flag": None},
    )
    assert resp.status_code == 200
    assert resp.json()["ocr_flag"] is None


def test_delete_material(client, auth_headers, price_list, sample_materials):
    mat_id = sample_materials[0].id
    resp = client.delete(f"/api/materials/{mat_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/materials/{mat_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_list_categories(client, auth_headers, price_list, sample_materials):
    resp = client.get("/api/materials/categories", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    cats = [c["category"] for c in data]
    assert "Fasteners" in cats
    assert "Shingles" in cats


def test_list_materials_requires_auth(client):
    resp = client.get("/api/materials")
    assert resp.status_code == 401
