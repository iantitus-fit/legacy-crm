from decimal import Decimal


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post(
        "/api/contacts", json={"name": name, "email": "test@example.com", "phone": "555-1234"}, headers=auth_headers
    )
    return resp.json()


def _create_job(client, auth_headers, seeded_stages, **overrides):
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
        "property_address": "123 Main St",
        **overrides,
    }
    resp = client.post("/api/jobs", json=data, headers=auth_headers)
    return resp.json()


def _create_estimate(client, auth_headers, job_id, **overrides):
    data = {"job_id": job_id, "name": "Test Estimate", **overrides}
    resp = client.post("/api/estimates", json=data, headers=auth_headers)
    return resp.json()


def _add_line_item(client, auth_headers, estimate_id, **overrides):
    data = {
        "description": "Shingles",
        "qty": "3.00",
        "unit_price": "100.00",
        **overrides,
    }
    resp = client.post(
        f"/api/estimates/{estimate_id}/line-items",
        json=data,
        headers=auth_headers,
    )
    return resp.json()


def _approve_estimate(client, auth_headers, estimate_id):
    """Set estimate status to approved."""
    resp = client.put(
        f"/api/estimates/{estimate_id}",
        json={"status": "approved"},
        headers=auth_headers,
    )
    # The estimate update endpoint doesn't have a 'status' field in EstimateUpdate
    # so we need to use direct DB update or a different approach
    # Actually, looking at the router, EstimateUpdate doesn't include status
    # Let's check if there's an approve endpoint
    return resp


def _set_estimate_approved(client, auth_headers, db_session, estimate_id):
    """Directly set estimate status to approved in DB for testing."""
    from app.models.estimate import Estimate
    est = db_session.query(Estimate).filter(Estimate.id == estimate_id).first()
    est.status = "approved"
    db_session.commit()


def _create_approved_estimate(client, auth_headers, seeded_stages, db_session):
    """Helper: create a job, estimate with line items, and approve it."""
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    _add_line_item(client, auth_headers, est["id"], description="Shingles", qty="10", unit_price="50.00")
    _add_line_item(client, auth_headers, est["id"], description="Nails", qty="5", unit_price="20.00")
    _set_estimate_approved(client, auth_headers, db_session, est["id"])
    return job, est


# --- Create Invoice ---


def test_create_invoice_from_estimate(client, auth_headers, seeded_stages, db_session):
    job, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    resp = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["invoice_number"] == "INV-0001"
    assert data["job_id"] == job["id"]
    assert data["estimate_id"] == est["id"]
    assert len(data["items"]) == 2
    assert data["contact_name"] == "Test Customer"
    assert data["job_address"] == "123 Main St"

    # Verify totals: subtotal = 500 + 100 = 600, tax = 600 * 0.07 = 42, total = 642
    assert Decimal(data["subtotal"]) == Decimal("600.00")
    assert Decimal(data["tax"]) == Decimal("42.00")
    assert Decimal(data["total"]) == Decimal("642.00")
    assert Decimal(data["balance"]) == Decimal("642.00")
    assert Decimal(data["amount_paid"]) == Decimal("0.00")


def test_create_invoice_requires_approved_estimate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])

    resp = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "approved" in resp.json()["detail"].lower()


def test_create_invoice_duplicate_prevention(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    resp1 = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"].lower()


def test_create_invoice_estimate_not_found(client, auth_headers):
    resp = client.post(
        "/api/invoices",
        json={"estimate_id": 9999},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_invoice_number_sequential(client, auth_headers, seeded_stages, db_session):
    """Invoice numbers increment: INV-0001, INV-0002, etc."""
    job = _create_job(client, auth_headers, seeded_stages)

    # Create two approved estimates
    est1 = _create_estimate(client, auth_headers, job["id"], name="Est 1")
    _add_line_item(client, auth_headers, est1["id"])
    _set_estimate_approved(client, auth_headers, db_session, est1["id"])

    est2 = _create_estimate(client, auth_headers, job["id"], name="Est 2")
    _add_line_item(client, auth_headers, est2["id"])
    _set_estimate_approved(client, auth_headers, db_session, est2["id"])

    resp1 = client.post(
        "/api/invoices",
        json={"estimate_id": est1["id"]},
        headers=auth_headers,
    )
    resp2 = client.post(
        "/api/invoices",
        json={"estimate_id": est2["id"]},
        headers=auth_headers,
    )

    assert resp1.json()["invoice_number"] == "INV-0001"
    assert resp2.json()["invoice_number"] == "INV-0002"


def test_create_invoice_copies_change_order_items(client, auth_headers, seeded_stages, db_session):
    """Approved CO items get copied with source_type='change_order' and co_number."""
    job, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    # Create a change order
    co_resp = client.post(
        f"/api/estimates/{est['id']}/change-orders",
        json={"name": "Add skylight"},
        headers=auth_headers,
    )
    co = co_resp.json()

    # Add item to CO
    client.post(
        f"/api/change-orders/{co['id']}/items",
        json={"description": "Skylight", "qty": "1", "unit_price": "500.00"},
        headers=auth_headers,
    )

    # Approve the CO
    from app.models.change_order import ChangeOrder
    co_obj = db_session.query(ChangeOrder).filter(ChangeOrder.id == co["id"]).first()
    co_obj.status = "approved"
    db_session.commit()

    resp = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()

    # 2 estimate items + 1 CO item
    assert len(data["items"]) == 3

    co_items = [i for i in data["items"] if i["source_type"] == "change_order"]
    assert len(co_items) == 1
    assert co_items[0]["description"] == "Skylight"
    assert co_items[0]["source_co_number"] == co["co_number"]

    est_items = [i for i in data["items"] if i["source_type"] == "estimate"]
    assert len(est_items) == 2


# --- Get / List ---


def test_get_invoice(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["invoice_number"] == "INV-0001"


def test_get_invoice_not_found(client, auth_headers):
    resp = client.get("/api/invoices/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_list_invoices(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )

    resp = client.get("/api/invoices", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_list_invoices_by_status(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )

    resp = client.get("/api/invoices", params={"status": "draft"}, headers=auth_headers)
    assert resp.json()["total"] == 1

    resp = client.get("/api/invoices", params={"status": "sent"}, headers=auth_headers)
    assert resp.json()["total"] == 0


def test_list_invoices_by_estimate_id(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    resp = client.get("/api/invoices", params={"estimate_id": est["id"]}, headers=auth_headers)
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["id"] == inv["id"]

    resp = client.get("/api/invoices", params={"estimate_id": 9999}, headers=auth_headers)
    assert resp.json()["total"] == 0


def test_list_invoices_search(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )

    resp = client.get("/api/invoices", params={"search": "INV-0001"}, headers=auth_headers)
    assert resp.json()["total"] == 1

    resp = client.get("/api/invoices", params={"search": "Main St"}, headers=auth_headers)
    assert resp.json()["total"] == 1

    resp = client.get("/api/invoices", params={"search": "nonexistent"}, headers=auth_headers)
    assert resp.json()["total"] == 0


# --- Update ---


def test_update_invoice(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    resp = client.put(
        f"/api/invoices/{inv['id']}",
        json={"notes": "Payment due on completion", "due_date": "2026-04-25"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["notes"] == "Payment due on completion"
    assert data["due_date"] == "2026-04-25"


def test_update_invoice_status(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    resp = client.put(
        f"/api/invoices/{inv['id']}",
        json={"status": "void"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "void"


# --- Delete ---


def test_delete_draft_invoice(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    resp = client.delete(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_non_draft_invoice_fails(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    # Set to sent
    client.put(
        f"/api/invoices/{inv['id']}",
        json={"status": "sent"},
        headers=auth_headers,
    )

    resp = client.delete(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert resp.status_code == 400
    assert "draft" in resp.json()["detail"].lower()


def test_delete_invoice_not_found(client, auth_headers):
    resp = client.delete("/api/invoices/9999", headers=auth_headers)
    assert resp.status_code == 404


# --- Invoice Item CRUD ---


def test_add_invoice_item(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    resp = client.post(
        f"/api/invoices/{inv['id']}/items",
        json={"description": "Extra materials", "qty": "2", "unit_price": "75.00"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    item = resp.json()
    assert item["description"] == "Extra materials"
    assert Decimal(item["line_total"]) == Decimal("150.00")

    # Verify totals recalculated
    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    # Original: subtotal=600, now +150 = 750
    assert Decimal(inv_resp.json()["subtotal"]) == Decimal("750.00")


def test_update_invoice_item(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    item_id = inv["items"][0]["id"]
    resp = client.put(
        f"/api/invoices/{inv['id']}/items/{item_id}",
        json={"qty": "20"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["line_total"]) == Decimal("1000.00")


def test_delete_invoice_item(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    item_id = inv["items"][0]["id"]
    resp = client.delete(
        f"/api/invoices/{inv['id']}/items/{item_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    # Verify recalculation (one item removed)
    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert len(inv_resp.json()["items"]) == 1
    # Only "Nails" remains: 5 * 20 = 100
    assert Decimal(inv_resp.json()["subtotal"]) == Decimal("100.00")


def test_invoice_item_not_found(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    resp = client.put(
        f"/api/invoices/{inv['id']}/items/9999",
        json={"qty": "5"},
        headers=auth_headers,
    )
    assert resp.status_code == 404

    resp = client.delete(
        f"/api/invoices/{inv['id']}/items/9999",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# --- Recalculation ---


def test_invoice_recalculation(client, auth_headers, seeded_stages, db_session):
    """Verify subtotal, tax, total, balance recalculate on item changes."""
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    # Initial: subtotal=600, tax=42, total=642, balance=642
    assert Decimal(inv["subtotal"]) == Decimal("600.00")
    assert Decimal(inv["tax"]) == Decimal("42.00")
    assert Decimal(inv["total"]) == Decimal("642.00")
    assert Decimal(inv["balance"]) == Decimal("642.00")

    # Add item
    client.post(
        f"/api/invoices/{inv['id']}/items",
        json={"description": "Underlayment", "qty": "4", "unit_price": "25.00"},
        headers=auth_headers,
    )

    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers).json()
    # subtotal = 600 + 100 = 700, tax = 700 * 0.07 = 49, total = 749
    assert Decimal(inv_resp["subtotal"]) == Decimal("700.00")
    assert Decimal(inv_resp["tax"]) == Decimal("49.00")
    assert Decimal(inv_resp["total"]) == Decimal("749.00")
    assert Decimal(inv_resp["balance"]) == Decimal("749.00")


# --- Auth ---


def test_invoices_require_auth(client):
    resp = client.get("/api/invoices")
    assert resp.status_code == 401

    resp = client.post("/api/invoices", json={"estimate_id": 1})
    assert resp.status_code == 401


# --- Estimate response includes invoice_id ---


def test_estimate_includes_invoice_id(client, auth_headers, seeded_stages, db_session):
    _, est = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    # Before invoice created
    est_resp = client.get(f"/api/estimates/{est['id']}", headers=auth_headers)
    assert est_resp.json()["invoice_id"] is None

    # Create invoice
    inv = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    ).json()

    # After invoice created
    est_resp = client.get(f"/api/estimates/{est['id']}", headers=auth_headers)
    assert est_resp.json()["invoice_id"] == inv["id"]


# --- Sprint 15a: Deposit invoices ---


def test_create_deposit_invoice(client, auth_headers, seeded_stages, db_session):
    """Deposit invoice creates a single-line invoice without changing estimate status."""
    from decimal import Decimal
    from app.models.estimate import Estimate

    job = _create_job(client, auth_headers, seeded_stages)
    est_resp = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "With Deposit"},
        headers=auth_headers,
    )
    est = est_resp.json()
    # Line item for 1000
    client.post(
        f"/api/estimates/{est['id']}/line-items",
        json={"description": "Work", "qty": "1", "unit_price": "1000.00"},
        headers=auth_headers,
    )

    # Put estimate in 'sent' so we're clearly not approved
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = "sent"
    db_session.commit()

    resp = client.post(
        "/api/invoices/deposit",
        json={"estimate_id": est["id"], "deposit_percent": "50"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    inv = resp.json()
    assert inv["is_deposit"] is True
    assert len(inv["items"]) == 1
    # 50% of (1000 + 70 tax) = 535
    assert Decimal(str(inv["items"][0]["line_total"])) == Decimal("535.00")
    assert Decimal(str(inv["total"])) == Decimal("535.00")
    assert Decimal(str(inv["balance"])) == Decimal("535.00")

    # Estimate status unchanged
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    assert est_obj.status == "sent"


def test_deposit_invoice_coexists_with_final_invoice(
    client, auth_headers, seeded_stages, db_session
):
    """A deposit invoice should not block creation of a final invoice."""
    from decimal import Decimal
    from app.models.estimate import Estimate

    job = _create_job(client, auth_headers, seeded_stages)
    est = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Deposit+Final"},
        headers=auth_headers,
    ).json()
    client.post(
        f"/api/estimates/{est['id']}/line-items",
        json={"description": "Work", "qty": "1", "unit_price": "500.00"},
        headers=auth_headers,
    )

    # Create deposit first
    resp = client.post(
        "/api/invoices/deposit",
        json={"estimate_id": est["id"], "deposit_percent": "25"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    # Approve and create final invoice
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = "approved"
    db_session.commit()

    final_resp = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )
    assert final_resp.status_code == 201
    assert final_resp.json()["is_deposit"] is False


def test_deposit_invoice_rejects_zero_estimate(
    client, auth_headers, seeded_stages
):
    job = _create_job(client, auth_headers, seeded_stages)
    est = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Empty"},
        headers=auth_headers,
    ).json()

    resp = client.post(
        "/api/invoices/deposit",
        json={"estimate_id": est["id"], "deposit_percent": "50"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "positive total" in resp.json()["detail"].lower()


def test_deposit_invoice_rejects_invalid_percent(
    client, auth_headers, seeded_stages
):
    job = _create_job(client, auth_headers, seeded_stages)
    est = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "X"},
        headers=auth_headers,
    ).json()
    client.post(
        f"/api/estimates/{est['id']}/line-items",
        json={"description": "Work", "qty": "1", "unit_price": "100.00"},
        headers=auth_headers,
    )

    resp = client.post(
        "/api/invoices/deposit",
        json={"estimate_id": est["id"], "deposit_percent": "150"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# --- Sprint 15.5a: tax_included invoice tests ---


def test_invoice_from_tax_included_estimate(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"], tax_included=True)
    _add_line_item(client, auth_headers, est["id"], qty="10", unit_price="50.00")
    _set_estimate_approved(client, auth_headers, db_session, est["id"])

    resp = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    invoice = resp.json()
    assert Decimal(str(invoice["tax_rate"])) == Decimal("0")
    assert Decimal(str(invoice["tax"])) == Decimal("0")
    assert Decimal(str(invoice["total"])) == Decimal("500.00")


def test_deposit_invoice_from_tax_included_estimate(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"], tax_included=True)
    _add_line_item(client, auth_headers, est["id"], qty="10", unit_price="100.00")

    resp = client.post(
        "/api/invoices/deposit",
        json={"estimate_id": est["id"], "deposit_percent": "50"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    invoice = resp.json()
    assert invoice["is_deposit"] is True
    assert Decimal(str(invoice["tax_rate"])) == Decimal("0")
    assert Decimal(str(invoice["tax"])) == Decimal("0")
    assert Decimal(str(invoice["total"])) == Decimal("500.00")
