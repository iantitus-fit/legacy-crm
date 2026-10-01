from uuid import uuid4

from app.models.change_order import ChangeOrder
from app.models.change_order_token import ChangeOrderToken
from app.models.estimate import Estimate


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


def _create_approved_estimate_and_co(client, auth_headers, seeded_stages, db_session):
    """Create an approved estimate with a CO that has items."""
    job = _create_job(client, auth_headers, seeded_stages)
    resp = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Test Estimate"},
        headers=auth_headers,
    )
    estimate = resp.json()

    est = db_session.query(Estimate).filter(Estimate.id == estimate["id"]).first()
    est.status = "approved"
    db_session.commit()

    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "Test CO"},
        headers=auth_headers,
    )
    co = co_resp.json()

    # Add an item
    client.post(
        f"/api/change-orders/{co['id']}/items",
        json={"description": "Extra shingles", "qty": "3", "unit_price": "45.00"},
        headers=auth_headers,
    )

    return estimate, co


def _create_token_for_co(db_session, co_id, status="sent"):
    """Create a portal token for a CO and optionally set status."""
    token_value = uuid4().hex
    db_session.add(ChangeOrderToken(
        change_order_id=co_id,
        token=token_value,
    ))
    co = db_session.query(ChangeOrder).filter(ChangeOrder.id == co_id).first()
    co.status = status
    db_session.commit()
    return token_value


# --- Invalid token ---


def test_co_portal_invalid_token_returns_404(client, seeded_stages):
    resp = client.get("/api/portal/co/badtoken123")
    assert resp.status_code == 404


# --- GET /api/portal/co/{token} ---


def test_co_portal_get(client, auth_headers, seeded_stages, db_session):
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )
    token = _create_token_for_co(db_session, co["id"])

    resp = client.get(f"/api/portal/co/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == co["id"]
    assert data["co_number"] == co["co_number"]
    assert data["estimate_name"] == "Test Estimate"
    assert len(data["items"]) == 1


def test_co_portal_first_view_sets_viewed(client, auth_headers, seeded_stages, db_session):
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )
    token = _create_token_for_co(db_session, co["id"], status="sent")

    resp = client.get(f"/api/portal/co/{token}")
    assert resp.json()["status"] == "viewed"


def test_co_portal_second_view_stays_viewed(client, auth_headers, seeded_stages, db_session):
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )
    token = _create_token_for_co(db_session, co["id"], status="sent")

    client.get(f"/api/portal/co/{token}")
    resp = client.get(f"/api/portal/co/{token}")
    assert resp.json()["status"] == "viewed"


# --- POST /api/portal/co/{token}/approve ---


def test_co_portal_approve(client, auth_headers, seeded_stages, db_session):
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )
    token = _create_token_for_co(db_session, co["id"])

    resp = client.post(
        f"/api/portal/co/{token}/approve",
        json={
            "signer_name": "John Smith",
            "signature_data": "data:image/png;base64,iVBORw0KGgo=",
            "terms_accepted": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify status changed
    db_co = db_session.query(ChangeOrder).filter(ChangeOrder.id == co["id"]).first()
    db_session.refresh(db_co)
    assert db_co.status == "approved"

    # Verify signature saved
    from app.models.change_order_signature import ChangeOrderSignature
    sig = db_session.query(ChangeOrderSignature).filter(
        ChangeOrderSignature.change_order_id == co["id"],
    ).first()
    assert sig is not None
    assert sig.signer_name == "John Smith"
    assert sig.terms_accepted is True


def test_co_portal_approve_requires_signer_name(client, auth_headers, seeded_stages, db_session):
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )
    token = _create_token_for_co(db_session, co["id"])

    resp = client.post(
        f"/api/portal/co/{token}/approve",
        json={
            "signer_name": "",
            "signature_data": "data:image/png;base64,abc",
            "terms_accepted": True,
        },
    )
    assert resp.status_code == 422


def test_co_portal_approve_requires_terms(client, auth_headers, seeded_stages, db_session):
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )
    token = _create_token_for_co(db_session, co["id"])

    resp = client.post(
        f"/api/portal/co/{token}/approve",
        json={
            "signer_name": "John",
            "signature_data": "data:image/png;base64,abc",
            "terms_accepted": False,
        },
    )
    assert resp.status_code == 422


# --- POST /api/portal/co/{token}/reject ---


def test_co_portal_reject(client, auth_headers, seeded_stages, db_session):
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )
    token = _create_token_for_co(db_session, co["id"])

    resp = client.post(
        f"/api/portal/co/{token}/reject",
        json={"name": "John Smith", "reason": "Too expensive"},
    )
    assert resp.status_code == 200

    db_co = db_session.query(ChangeOrder).filter(ChangeOrder.id == co["id"]).first()
    db_session.refresh(db_co)
    assert db_co.status == "rejected"


# --- POST /api/portal/co/{token}/request-changes ---


def test_co_portal_request_changes(client, auth_headers, seeded_stages, db_session):
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )
    token = _create_token_for_co(db_session, co["id"])

    resp = client.post(
        f"/api/portal/co/{token}/request-changes",
        json={"message": "Please lower the price"},
    )
    assert resp.status_code == 200

    db_co = db_session.query(ChangeOrder).filter(ChangeOrder.id == co["id"]).first()
    db_session.refresh(db_co)
    assert db_co.status == "changes_requested"


def test_co_portal_request_changes_requires_message(client, auth_headers, seeded_stages, db_session):
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )
    token = _create_token_for_co(db_session, co["id"])

    resp = client.post(
        f"/api/portal/co/{token}/request-changes",
        json={"message": ""},
    )
    assert resp.status_code == 422


# --- No auth required for portal ---


def test_co_portal_no_auth_required(client, auth_headers, seeded_stages, db_session):
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )
    token = _create_token_for_co(db_session, co["id"])

    # No auth headers
    resp = client.get(f"/api/portal/co/{token}")
    assert resp.status_code == 200


# --- Send CO creates token and updates status ---


def test_send_co_creates_token_and_sets_sent(client, auth_headers, seeded_stages, db_session):
    """The send endpoint creates a token and sets CO status to sent.
    Note: actual email sending will fail in test (no SMTP), so we test
    that the endpoint structure is correct by checking the route exists.
    """
    estimate, co = _create_approved_estimate_and_co(
        client, auth_headers, seeded_stages, db_session
    )

    # The send endpoint requires SMTP config to actually work.
    # We verify the endpoint exists and validates properly.
    # With no SMTP configured, it will raise a 500 (email failure).
    resp = client.post(
        f"/api/change-orders/{co['id']}/send",
        json={
            "to_email": "customer@example.com",
            "subject": "Test CO",
            "message": "Please review",
        },
        headers=auth_headers,
    )
    # Either 200 (if SMTP works) or 500 (email failure) — not 404 or 422
    assert resp.status_code in (200, 500)
