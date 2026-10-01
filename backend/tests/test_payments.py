from decimal import Decimal


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post(
        "/api/contacts",
        json={"name": name, "email": "test@example.com", "phone": "555-1234"},
        headers=auth_headers,
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


def _create_approved_estimate_and_invoice(client, auth_headers, seeded_stages, db_session):
    """Helper: create job, approved estimate with items, and an invoice."""
    from app.models.estimate import Estimate

    job = _create_job(client, auth_headers, seeded_stages)
    est_resp = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Test Estimate"},
        headers=auth_headers,
    )
    est = est_resp.json()
    client.post(
        f"/api/estimates/{est['id']}/line-items",
        json={"description": "Shingles", "qty": "10", "unit_price": "100.00"},
        headers=auth_headers,
    )
    # Approve estimate directly in DB
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = "approved"
    db_session.commit()

    inv_resp = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )
    inv = inv_resp.json()
    # Invoice total: subtotal=1000, tax=70, total=1070
    return job, est, inv


# --- Record Payment ---


def test_record_payment(client, auth_headers, seeded_stages, db_session):
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )

    resp = client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={
            "date_received": "2026-03-24",
            "amount": "500.00",
            "method": "check",
            "reference": "1234",
            "notes": "Deposit",
            "is_deposit": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    payment = resp.json()
    assert Decimal(payment["amount"]) == Decimal("500.00")
    assert payment["method"] == "check"
    assert payment["reference"] == "1234"
    assert payment["is_deposit"] is True

    # Verify invoice updated
    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    inv_data = inv_resp.json()
    assert Decimal(inv_data["amount_paid"]) == Decimal("500.00")
    assert Decimal(inv_data["balance"]) == Decimal("570.00")
    assert inv_data["status"] == "partial"


def test_record_payment_full_amount_marks_paid(client, auth_headers, seeded_stages, db_session):
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )
    total = Decimal(inv["total"])

    resp = client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={
            "date_received": "2026-03-24",
            "amount": str(total),
            "method": "ach",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201

    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    inv_data = inv_resp.json()
    assert inv_data["status"] == "paid"
    assert Decimal(inv_data["balance"]) == Decimal("0.00")
    assert Decimal(inv_data["amount_paid"]) == total


def test_record_payment_zero_amount_rejected(client, auth_headers, seeded_stages, db_session):
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )

    resp = client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-24", "amount": "0", "method": "cash"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "greater than zero" in resp.json()["detail"].lower()


def test_record_payment_on_void_invoice_rejected(client, auth_headers, seeded_stages, db_session):
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )

    # Void the invoice
    client.put(
        f"/api/invoices/{inv['id']}",
        json={"status": "void"},
        headers=auth_headers,
    )

    resp = client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-24", "amount": "100", "method": "cash"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "void" in resp.json()["detail"].lower()


def test_record_payment_invoice_not_found(client, auth_headers):
    resp = client.post(
        "/api/invoices/9999/payments",
        json={"date_received": "2026-03-24", "amount": "100", "method": "cash"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# --- List Payments ---


def test_list_payments(client, auth_headers, seeded_stages, db_session):
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )

    client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-24", "amount": "200", "method": "cash"},
        headers=auth_headers,
    )
    client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-25", "amount": "300", "method": "check"},
        headers=auth_headers,
    )

    resp = client.get(f"/api/invoices/{inv['id']}/payments", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert Decimal(data["items"][0]["amount"]) == Decimal("200.00")
    assert Decimal(data["items"][1]["amount"]) == Decimal("300.00")


def test_list_payments_invoice_not_found(client, auth_headers):
    resp = client.get("/api/invoices/9999/payments", headers=auth_headers)
    assert resp.status_code == 404


# --- Update Payment ---


def test_update_payment(client, auth_headers, seeded_stages, db_session):
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )

    pay_resp = client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-24", "amount": "500", "method": "check"},
        headers=auth_headers,
    )
    pay = pay_resp.json()

    resp = client.put(
        f"/api/invoices/{inv['id']}/payments/{pay['id']}",
        json={"amount": "600", "reference": "5678"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["amount"]) == Decimal("600.00")
    assert resp.json()["reference"] == "5678"

    # Verify invoice recalculated
    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert Decimal(inv_resp.json()["amount_paid"]) == Decimal("600.00")


def test_update_payment_recalculates_status(client, auth_headers, seeded_stages, db_session):
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )
    total = Decimal(inv["total"])

    # Record full payment → paid
    pay_resp = client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-24", "amount": str(total), "method": "ach"},
        headers=auth_headers,
    )
    pay = pay_resp.json()
    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert inv_resp.json()["status"] == "paid"

    # Reduce amount → partial
    client.put(
        f"/api/invoices/{inv['id']}/payments/{pay['id']}",
        json={"amount": "100"},
        headers=auth_headers,
    )
    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert inv_resp.json()["status"] == "partial"


def test_update_payment_not_found(client, auth_headers, seeded_stages, db_session):
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )
    resp = client.put(
        f"/api/invoices/{inv['id']}/payments/9999",
        json={"amount": "100"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# --- Delete Payment ---


def test_delete_payment(client, auth_headers, seeded_stages, db_session):
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )

    pay_resp = client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-24", "amount": "500", "method": "cash"},
        headers=auth_headers,
    )
    pay = pay_resp.json()
    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert inv_resp.json()["status"] == "partial"

    resp = client.delete(
        f"/api/invoices/{inv['id']}/payments/{pay['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    # Verify invoice recalculated — back to draft (never sent)
    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert inv_resp.json()["status"] == "draft"
    assert Decimal(inv_resp.json()["amount_paid"]) == Decimal("0.00")
    assert Decimal(inv_resp.json()["balance"]) == Decimal(inv["total"])


def test_delete_payment_reverts_to_sent(client, auth_headers, seeded_stages, db_session):
    """When all payments deleted and invoice was previously sent, status reverts to sent."""
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )

    # Set invoice to sent with a date
    client.put(
        f"/api/invoices/{inv['id']}",
        json={"status": "sent", "date_invoiced": "2026-03-20"},
        headers=auth_headers,
    )

    pay_resp = client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-24", "amount": "200", "method": "cash"},
        headers=auth_headers,
    )
    pay = pay_resp.json()

    client.delete(
        f"/api/invoices/{inv['id']}/payments/{pay['id']}",
        headers=auth_headers,
    )

    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert inv_resp.json()["status"] == "sent"


def test_delete_payment_not_found(client, auth_headers, seeded_stages, db_session):
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )
    resp = client.delete(
        f"/api/invoices/{inv['id']}/payments/9999",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# --- Multiple Payments ---


def test_multiple_payments_partial_then_paid(client, auth_headers, seeded_stages, db_session):
    """Two partial payments that together equal the total → paid."""
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )
    total = Decimal(inv["total"])
    half = (total / 2).quantize(Decimal("0.01"))
    remainder = total - half

    client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-24", "amount": str(half), "method": "check"},
        headers=auth_headers,
    )
    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert inv_resp.json()["status"] == "partial"

    client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-25", "amount": str(remainder), "method": "cash"},
        headers=auth_headers,
    )
    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert inv_resp.json()["status"] == "paid"
    assert Decimal(inv_resp.json()["balance"]) == Decimal("0.00")


# --- Void Protection ---


def test_void_status_not_changed_by_payment_recalc(client, auth_headers, seeded_stages, db_session):
    """Voided invoice status should not change even if payments exist."""
    _, _, inv = _create_approved_estimate_and_invoice(
        client, auth_headers, seeded_stages, db_session
    )

    # Record a payment first
    pay_resp = client.post(
        f"/api/invoices/{inv['id']}/payments",
        json={"date_received": "2026-03-24", "amount": "200", "method": "cash"},
        headers=auth_headers,
    )

    # Now void the invoice
    client.put(
        f"/api/invoices/{inv['id']}",
        json={"status": "void"},
        headers=auth_headers,
    )

    # Delete the payment — should not change void status
    pay = pay_resp.json()
    client.delete(
        f"/api/invoices/{inv['id']}/payments/{pay['id']}",
        headers=auth_headers,
    )

    inv_resp = client.get(f"/api/invoices/{inv['id']}", headers=auth_headers)
    assert inv_resp.json()["status"] == "void"


# --- Auth ---


def test_payments_require_auth(client, seeded_stages):
    resp = client.get("/api/invoices/1/payments")
    assert resp.status_code == 401

    resp = client.post(
        "/api/invoices/1/payments",
        json={"date_received": "2026-03-24", "amount": "100", "method": "cash"},
    )
    assert resp.status_code == 401
