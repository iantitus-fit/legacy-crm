import pytest
from decimal import Decimal

from app.models.material import Material
from app.models.price_list import PriceList


@pytest.fixture()
def price_lists(db_session):
    pls = [
        PriceList(name="ABC Roofing", source_file="roofing.csv"),
        PriceList(name="Mastic Siding/Trim", source_file="siding.csv"),
    ]
    db_session.add_all(pls)
    db_session.commit()
    mat = Material(
        price_list_id=pls[0].id,
        item_number="T001",
        description="Test",
        unit_price=Decimal("10.00"),
        category="Shingles",
    )
    db_session.add(mat)
    db_session.commit()
    return pls


def test_list_price_lists(client, auth_headers, price_lists):
    resp = client.get("/api/price-lists", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    abc = next(i for i in data["items"] if i["name"] == "ABC Roofing")
    assert abc["material_count"] == 1


def test_update_price_list(client, auth_headers, price_lists):
    pl_id = price_lists[0].id
    resp = client.put(
        f"/api/price-lists/{pl_id}",
        headers=auth_headers,
        json={"expiration_date": "2026-06-01"},
    )
    assert resp.status_code == 200
    assert resp.json()["expiration_date"] == "2026-06-01"


def test_update_price_list_not_found(client, auth_headers):
    resp = client.put(
        "/api/price-lists/99999",
        headers=auth_headers,
        json={"name": "X"},
    )
    assert resp.status_code == 404
