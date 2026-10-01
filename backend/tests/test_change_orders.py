from decimal import Decimal


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post("/api/contacts", json={"name": name}, headers=auth_headers)
    return resp.json()


def _create_job(client, auth_headers, seeded_stages):
    contact = _create_contact(client, auth_headers)
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    data = {
        "pipeline_id": pipeline["id"],
        "contact_id": contact["id"],
        "stage_id": stages[0]["id"],
        "work_type": "retail",
    }
    resp = client.post("/api/jobs", json=data, headers=auth_headers)
    return resp.json()


def _create_approved_estimate(client, auth_headers, seeded_stages, db_session):
    """Create an estimate and set it to approved status."""
    job = _create_job(client, auth_headers, seeded_stages)
    resp = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Test Estimate"},
        headers=auth_headers,
    )
    estimate = resp.json()

    # Set estimate to approved via DB
    from app.models.estimate import Estimate
    est = db_session.query(Estimate).filter(Estimate.id == estimate["id"]).first()
    est.status = "approved"
    db_session.commit()

    return estimate


# --- Create Change Order ---


def test_create_change_order_on_approved_estimate(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Color upgrade"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["co_number"] == 1
    assert data["name"] == "Color upgrade"
    assert data["status"] == "draft"
    assert data["items"] == []


def test_create_change_order_on_non_approved_fails(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Draft Estimate"},
        headers=auth_headers,
    )
    estimate = resp.json()

    resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Should fail"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "approved" in resp.json()["detail"].lower()


def test_co_number_auto_increments(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    resp1 = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "CO 1"},
        headers=auth_headers,
    )
    resp2 = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "CO 2"},
        headers=auth_headers,
    )
    assert resp1.json()["co_number"] == 1
    assert resp2.json()["co_number"] == 2


# --- List / Get / Update / Delete ---


def test_list_change_orders(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "CO A"},
        headers=auth_headers,
    )
    client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "CO B"},
        headers=auth_headers,
    )

    resp = client.get(
        f"/api/estimates/{estimate['id']}/change-orders",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["co_number"] == 1
    assert data[1]["co_number"] == 2


def test_get_change_order(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    create_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "My CO"},
        headers=auth_headers,
    )
    co_id = create_resp.json()["id"]

    resp = client.get(f"/api/change-orders/{co_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "My CO"


def test_update_change_order(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    create_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Old name"},
        headers=auth_headers,
    )
    co_id = create_resp.json()["id"]

    resp = client.put(
        f"/api/change-orders/{co_id}",
        json={"name": "New name", "status": "approved"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New name"
    assert resp.json()["status"] == "approved"


def test_delete_change_order(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    create_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "To delete"},
        headers=auth_headers,
    )
    co_id = create_resp.json()["id"]

    resp = client.delete(f"/api/change-orders/{co_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/change-orders/{co_id}", headers=auth_headers)
    assert resp.status_code == 404


# --- CO Item CRUD ---


def test_add_co_item(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "CO with items"},
        headers=auth_headers,
    )
    co_id = co_resp.json()["id"]

    resp = client.post(
        f"/api/change-orders/{co_id}/items",
        json={"description": "Extra shingles", "qty": "3", "unit_price": "45.00"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "Extra shingles"
    assert Decimal(str(data["line_total"])) == Decimal("135.00")


def test_update_co_item(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={},
        headers=auth_headers,
    )
    co_id = co_resp.json()["id"]

    item_resp = client.post(
        f"/api/change-orders/{co_id}/items",
        json={"description": "Item", "qty": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    resp = client.put(
        f"/api/change-orders/{co_id}/items/{item_id}",
        json={"qty": "5"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert Decimal(str(resp.json()["line_total"])) == Decimal("500.00")


def test_delete_co_item(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={},
        headers=auth_headers,
    )
    co_id = co_resp.json()["id"]

    item_resp = client.post(
        f"/api/change-orders/{co_id}/items",
        json={"description": "Item", "qty": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    resp = client.delete(
        f"/api/change-orders/{co_id}/items/{item_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    # CO subtotal should be 0
    co = client.get(f"/api/change-orders/{co_id}", headers=auth_headers).json()
    assert Decimal(str(co["subtotal"])) == Decimal("0")


# --- CO Calculation ---


def test_co_recalculates_on_item_changes(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Calc test"},
        headers=auth_headers,
    )
    co_id = co_resp.json()["id"]

    # Add two items
    client.post(
        f"/api/change-orders/{co_id}/items",
        json={"description": "A", "qty": "2", "unit_price": "100.00"},
        headers=auth_headers,
    )
    client.post(
        f"/api/change-orders/{co_id}/items",
        json={"description": "B", "qty": "1", "unit_price": "50.00"},
        headers=auth_headers,
    )

    co = client.get(f"/api/change-orders/{co_id}", headers=auth_headers).json()
    # subtotal = 200 + 50 = 250
    assert Decimal(str(co["subtotal"])) == Decimal("250.00")
    # tax = 250 * 0.07 = 17.50
    assert Decimal(str(co["tax"])) == Decimal("17.50")
    # total = 267.50
    assert Decimal(str(co["total"])) == Decimal("267.50")


# --- Estimate Response includes COs and grand_total ---


def test_estimate_response_includes_change_orders(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    # Create a CO with items
    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Test CO"},
        headers=auth_headers,
    )
    co_id = co_resp.json()["id"]

    client.post(
        f"/api/change-orders/{co_id}/items",
        json={"description": "Item", "qty": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )

    # Fetch the estimate
    resp = client.get(f"/api/estimates/{estimate['id']}", headers=auth_headers)
    data = resp.json()
    assert "change_orders" in data
    assert len(data["change_orders"]) == 1
    assert data["change_orders"][0]["co_number"] == 1
    assert data["change_orders"][0]["name"] == "Test CO"


def test_grand_total_includes_approved_cos_only(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    # Create two COs
    co1_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Approved CO"},
        headers=auth_headers,
    )
    co1_id = co1_resp.json()["id"]
    client.post(
        f"/api/change-orders/{co1_id}/items",
        json={"description": "Item", "qty": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )
    # Approve CO1
    client.put(
        f"/api/change-orders/{co1_id}",
        json={"status": "approved"},
        headers=auth_headers,
    )

    co2_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Draft CO"},
        headers=auth_headers,
    )
    co2_id = co2_resp.json()["id"]
    client.post(
        f"/api/change-orders/{co2_id}/items",
        json={"description": "Item", "qty": "1", "unit_price": "500.00"},
        headers=auth_headers,
    )

    # Fetch estimate
    resp = client.get(f"/api/estimates/{estimate['id']}", headers=auth_headers)
    data = resp.json()

    # Estimate total is 0 (no line items), approved CO total = 100 + 7 tax = 107
    estimate_total = Decimal(str(data["total"]))
    grand_total = Decimal(str(data["grand_total"]))
    co1_total = Decimal(str(data["change_orders"][0]["total"]))

    assert grand_total == estimate_total + co1_total
    # Draft CO should NOT be included in grand_total


def test_delete_co_cascades_items(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Cascade test"},
        headers=auth_headers,
    )
    co_id = co_resp.json()["id"]

    client.post(
        f"/api/change-orders/{co_id}/items",
        json={"description": "A", "qty": "1", "unit_price": "10.00"},
        headers=auth_headers,
    )
    client.post(
        f"/api/change-orders/{co_id}/items",
        json={"description": "B", "qty": "1", "unit_price": "20.00"},
        headers=auth_headers,
    )

    # Delete the CO
    resp = client.delete(f"/api/change-orders/{co_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Items should be gone too
    from app.models.change_order_item import ChangeOrderItem
    count = db_session.query(ChangeOrderItem).filter(
        ChangeOrderItem.change_order_id == co_id
    ).count()
    assert count == 0


def test_duplicate_co_item(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "CO"},
        headers=auth_headers,
    )
    co_id = co_resp.json()["id"]

    item_resp = client.post(
        f"/api/change-orders/{co_id}/items",
        json={
            "description": "Extra underlayment",
            "qty": "2",
            "unit_price": "75.00",
            "body": "<p>Synthetic</p>",
            "notes": "Bring extra",
        },
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]
    original_sort_order = item_resp.json()["sort_order"]

    resp = client.post(
        f"/api/change-orders/{co_id}/items/{item_id}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    dup = resp.json()
    assert dup["id"] != item_id
    assert dup["description"] == "Extra underlayment"
    assert Decimal(str(dup["qty"])) == Decimal("2")
    assert Decimal(str(dup["unit_price"])) == Decimal("75.00")
    assert Decimal(str(dup["line_total"])) == Decimal("150.00")
    assert dup["body"] == "<p>Synthetic</p>"
    assert dup["notes"] == "Bring extra"
    assert dup["sort_order"] > original_sort_order

    # CO subtotal doubled
    co = client.get(f"/api/change-orders/{co_id}", headers=auth_headers).json()
    assert Decimal(str(co["subtotal"])) == Decimal("300.00")
    assert Decimal(str(co["tax"])) == Decimal("21.00")  # 300 * 0.07 default tax rate
    assert Decimal(str(co["total"])) == Decimal("321.00")
    assert len(co["items"]) == 2


def test_duplicate_co_item_not_found(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={},
        headers=auth_headers,
    )
    co_id = co_resp.json()["id"]

    resp = client.post(
        f"/api/change-orders/{co_id}/items/9999/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_duplicate_co_item_wrong_co(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    co_a = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "A"},
        headers=auth_headers,
    ).json()
    co_b = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "B"},
        headers=auth_headers,
    ).json()

    item = client.post(
        f"/api/change-orders/{co_a['id']}/items",
        json={"description": "Item", "qty": "1", "unit_price": "10"},
        headers=auth_headers,
    ).json()

    resp = client.post(
        f"/api/change-orders/{co_b['id']}/items/{item['id']}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# --- Sprint 15.5b: accepted_at on change orders ---


def test_approved_co_with_signature_has_accepted_at(client, auth_headers, seeded_stages, db_session):
    from app.models.change_order_signature import ChangeOrderSignature

    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    co = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Upgrade"},
        headers=auth_headers,
    ).json()
    client.post(
        f"/api/change-orders/{co['id']}/items",
        json={"description": "Extra", "qty": "1", "unit_price": "50"},
        headers=auth_headers,
    )
    client.put(
        f"/api/change-orders/{co['id']}",
        json={"status": "approved"},
        headers=auth_headers,
    )

    db_session.add(ChangeOrderSignature(
        change_order_id=co["id"],
        signer_name="Test Customer",
        signature_data="data:image/png;base64,abc",
        terms_accepted=True,
    ))
    db_session.commit()

    resp = client.get(f"/api/estimates/{estimate['id']}", headers=auth_headers)
    co_data = next(c for c in resp.json()["change_orders"] if c["id"] == co["id"])
    assert co_data["accepted_at"] is not None


def test_non_approved_co_has_null_accepted_at(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    co = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Draft CO"},
        headers=auth_headers,
    ).json()

    resp = client.get(f"/api/estimates/{estimate['id']}", headers=auth_headers)
    co_data = next(c for c in resp.json()["change_orders"] if c["id"] == co["id"])
    assert co_data["accepted_at"] is None


def test_approved_co_without_signature_has_null_accepted_at(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    co = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Manual approve"},
        headers=auth_headers,
    ).json()
    client.put(
        f"/api/change-orders/{co['id']}",
        json={"status": "approved"},
        headers=auth_headers,
    )

    resp = client.get(f"/api/estimates/{estimate['id']}", headers=auth_headers)
    co_data = next(c for c in resp.json()["change_orders"] if c["id"] == co["id"])
    assert co_data["accepted_at"] is None
