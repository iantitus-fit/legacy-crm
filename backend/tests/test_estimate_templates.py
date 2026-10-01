from decimal import Decimal

import pytest

from app.models.estimate_template import EstimateTemplate
from app.models.estimate_template_item import EstimateTemplateItem
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
def sample_material(db_session, price_list):
    mat = Material(
        price_list_id=price_list.id,
        item_number="OC001",
        description="OC Duration Brownwood",
        unit_price=Decimal("117.96"),
        uom="BD",
        category="Shingles",
    )
    db_session.add(mat)
    db_session.commit()
    db_session.refresh(mat)
    return mat


@pytest.fixture()
def template(db_session):
    t = EstimateTemplate(
        name="IKO Cambridge 30-Year",
        description="Standard residential roof",
        default_margin_pct=Decimal("46.00"),
        default_waste_pct=Decimal("10.00"),
    )
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture()
def template_with_items(db_session, template, sample_material):
    items = [
        EstimateTemplateItem(
            template_id=template.id,
            material_id=sample_material.id,
            description="OC Duration Brownwood",
            category="Roofing",
            unit_cost=Decimal("117.96"),
            uom="BD",
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("10.00"),
            measurement_type="total_area",
            conversion_factor=Decimal("3.0000"),
            sort_order=0,
        ),
        EstimateTemplateItem(
            template_id=template.id,
            description="Roofing Labor",
            category="Labor",
            unit_cost=Decimal("500.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("0.00"),
            measurement_type=None,
            conversion_factor=Decimal("1.0000"),
            default_qty=Decimal("1.00"),
            sort_order=1,
        ),
    ]
    db_session.add_all(items)
    db_session.commit()
    return template


# --- List Templates ---

def test_list_templates(client, auth_headers, template):
    resp = client.get("/api/estimate-templates", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "IKO Cambridge 30-Year"
    assert data["items"][0]["item_count"] == 0


def test_list_templates_excludes_inactive(client, auth_headers, db_session):
    t = EstimateTemplate(name="Inactive", is_active=False)
    db_session.add(t)
    db_session.commit()
    resp = client.get("/api/estimate-templates", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# --- Get Template ---

def test_get_template(client, auth_headers, template_with_items):
    resp = client.get(
        f"/api/estimate-templates/{template_with_items.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "IKO Cambridge 30-Year"
    assert len(data["items"]) == 2
    assert data["items"][0]["description"] == "OC Duration Brownwood"
    assert data["items"][1]["description"] == "Roofing Labor"


def test_get_template_not_found(client, auth_headers):
    resp = client.get("/api/estimate-templates/99999", headers=auth_headers)
    assert resp.status_code == 404


# --- Create Template ---

def test_create_template(client, auth_headers):
    resp = client.post(
        "/api/estimate-templates",
        headers=auth_headers,
        json={
            "name": "OC Duration Storm",
            "description": "High-wind rated",
            "default_margin_pct": "50.00",
            "default_waste_pct": "12.00",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "OC Duration Storm"
    assert data["default_margin_pct"] == "50.00"


def test_create_template_duplicate_name(client, auth_headers, template):
    resp = client.post(
        "/api/estimate-templates",
        headers=auth_headers,
        json={"name": "IKO Cambridge 30-Year"},
    )
    assert resp.status_code == 400


# --- Update Template ---

def test_update_template(client, auth_headers, template):
    resp = client.put(
        f"/api/estimate-templates/{template.id}",
        headers=auth_headers,
        json={"name": "IKO Cambridge Updated", "default_margin_pct": "48.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "IKO Cambridge Updated"
    assert resp.json()["default_margin_pct"] == "48.00"


# --- Delete (soft) Template ---

def test_delete_template(client, auth_headers, template):
    resp = client.delete(
        f"/api/estimate-templates/{template.id}", headers=auth_headers
    )
    assert resp.status_code == 204
    resp = client.get("/api/estimate-templates", headers=auth_headers)
    assert resp.json()["total"] == 0


# --- Duplicate Template ---

def test_duplicate_template(client, auth_headers, template_with_items):
    resp = client.post(
        f"/api/estimate-templates/{template_with_items.id}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "IKO Cambridge 30-Year (Copy)"
    assert len(data["items"]) == 2
    assert data["id"] != template_with_items.id


# --- Add Item ---

def test_add_item(client, auth_headers, template, sample_material):
    resp = client.post(
        f"/api/estimate-templates/{template.id}/items",
        headers=auth_headers,
        json={
            "material_id": sample_material.id,
            "description": "OC Duration Brownwood",
            "category": "Roofing",
            "unit_cost": "117.96",
            "uom": "BD",
            "measurement_type": "total_area",
            "conversion_factor": "3.0000",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "OC Duration Brownwood"
    assert data["margin_pct"] == "46.00"  # inherited from template default


def test_add_manual_item(client, auth_headers, template):
    resp = client.post(
        f"/api/estimate-templates/{template.id}/items",
        headers=auth_headers,
        json={
            "description": "Dumpster Rental",
            "category": "Labor",
            "unit_cost": "350.00",
            "waste_pct": "0.00",
            "default_qty": "1.00",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["material_id"] is None
    assert resp.json()["default_qty"] == "1.00"


# --- Update Item ---

def test_update_item(client, auth_headers, template_with_items, db_session):
    item = (
        db_session.query(EstimateTemplateItem)
        .filter(EstimateTemplateItem.template_id == template_with_items.id)
        .first()
    )
    resp = client.put(
        f"/api/estimate-templates/{template_with_items.id}/items/{item.id}",
        headers=auth_headers,
        json={"waste_pct": "15.00", "margin_pct": "50.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["waste_pct"] == "15.00"
    assert resp.json()["margin_pct"] == "50.00"


# --- Delete Item ---

def test_delete_item(client, auth_headers, template_with_items, db_session):
    item = (
        db_session.query(EstimateTemplateItem)
        .filter(EstimateTemplateItem.template_id == template_with_items.id)
        .first()
    )
    resp = client.delete(
        f"/api/estimate-templates/{template_with_items.id}/items/{item.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204


# --- Reorder Items ---

def test_reorder_items(client, auth_headers, template_with_items, db_session):
    items = (
        db_session.query(EstimateTemplateItem)
        .filter(EstimateTemplateItem.template_id == template_with_items.id)
        .order_by(EstimateTemplateItem.sort_order)
        .all()
    )
    resp = client.put(
        f"/api/estimate-templates/{template_with_items.id}/items/reorder",
        headers=auth_headers,
        json={"item_ids": [items[1].id, items[0].id]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["description"] == "Roofing Labor"
    assert data["items"][1]["description"] == "OC Duration Brownwood"


# --- Preview ---

def test_preview(client, auth_headers, template_with_items):
    resp = client.post(
        f"/api/estimate-templates/{template_with_items.id}/preview",
        headers=auth_headers,
        json={
            "measurements": {
                "total_area": "32.5",
            }
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["item_count"] == 2
    assert data["items"][0]["qty"] == 108
    assert data["items"][1]["qty"] == 1
    assert Decimal(data["subtotal"]) > Decimal("0")


# --- Auth required ---

def test_templates_require_auth(client):
    resp = client.get("/api/estimate-templates")
    assert resp.status_code == 401
