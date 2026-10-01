"""Tests for GET /api/contacts/{contact_id}/activity (Sprint 15.6c)."""


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post(
        "/api/contacts", json={"name": name}, headers=auth_headers
    )
    return resp.json()


def _create_job(client, auth_headers, contact_id):
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    resp = client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "contact_id": contact_id,
            "stage_id": stages[0]["id"],
            "work_type": "retail",
        },
        headers=auth_headers,
    )
    return resp.json()


def _create_estimate(client, auth_headers, job_id, name="Roof"):
    resp = client.post(
        "/api/estimates",
        json={"job_id": job_id, "name": name},
        headers=auth_headers,
    )
    return resp.json()


def _approve_and_invoice(client, auth_headers, db_session, estimate_id):
    """Add a line item, approve the estimate in-DB, then create an invoice."""
    from app.models.estimate import Estimate

    client.post(
        f"/api/estimates/{estimate_id}/line-items",
        json={"description": "Work", "qty": "1", "unit_price": "1000.00"},
        headers=auth_headers,
    )
    est = db_session.query(Estimate).filter(Estimate.id == estimate_id).first()
    est.status = "approved"
    db_session.commit()
    resp = client.post(
        "/api/invoices",
        json={"estimate_id": estimate_id},
        headers=auth_headers,
    )
    return resp.json()


def _record_payment(client, auth_headers, invoice_id, amount="250.00"):
    resp = client.post(
        f"/api/invoices/{invoice_id}/payments",
        json={
            "amount": amount,
            "method": "check",
            "date_received": "2026-04-20",
        },
        headers=auth_headers,
    )
    return resp.json()


def test_activity_returns_estimate_created_event(
    client, auth_headers, seeded_stages
):
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, contact["id"])
    est = _create_estimate(client, auth_headers, job["id"])

    resp = client.get(
        f"/api/contacts/{contact['id']}/activity", headers=auth_headers
    )
    assert resp.status_code == 200
    events = resp.json()
    types = [e["type"] for e in events]
    assert "estimate_created" in types
    created = next(e for e in events if e["type"] == "estimate_created")
    assert created["entity_type"] == "estimate"
    assert created["entity_id"] == est["id"]


def test_activity_returns_invoice_and_payment_events(
    client, auth_headers, seeded_stages, db_session
):
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, contact["id"])
    est = _create_estimate(client, auth_headers, job["id"])
    inv = _approve_and_invoice(client, auth_headers, db_session, est["id"])
    _record_payment(client, auth_headers, inv["id"], amount="250.00")

    resp = client.get(
        f"/api/contacts/{contact['id']}/activity", headers=auth_headers
    )
    events = resp.json()
    types = [e["type"] for e in events]
    assert "invoice_created" in types
    assert "payment_received" in types
    payment_event = next(e for e in events if e["type"] == "payment_received")
    assert "250" in payment_event["description"]


def test_activity_returns_note_event(client, auth_headers, seeded_stages):
    contact = _create_contact(client, auth_headers)
    client.post(
        "/api/notes",
        json={
            "entity_type": "contact",
            "entity_id": contact["id"],
            "note_type": "company",
            "content": "Spoke with client",
        },
        headers=auth_headers,
    )

    resp = client.get(
        f"/api/contacts/{contact['id']}/activity", headers=auth_headers
    )
    events = resp.json()
    assert any(e["type"] == "note_added" for e in events)


def test_activity_sorted_by_timestamp_desc(
    client, auth_headers, seeded_stages
):
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, contact["id"])
    _create_estimate(client, auth_headers, job["id"], name="First")
    _create_estimate(client, auth_headers, job["id"], name="Second")

    resp = client.get(
        f"/api/contacts/{contact['id']}/activity", headers=auth_headers
    )
    events = resp.json()
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps, reverse=True)


def test_activity_respects_limit(client, auth_headers, seeded_stages):
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, contact["id"])
    for i in range(5):
        _create_estimate(client, auth_headers, job["id"], name=f"Est {i}")

    resp = client.get(
        f"/api/contacts/{contact['id']}/activity?limit=3", headers=auth_headers
    )
    assert len(resp.json()) == 3


def test_activity_excludes_other_contact_events(
    client, auth_headers, seeded_stages
):
    contact_a = _create_contact(client, auth_headers, "Client A")
    contact_b = _create_contact(client, auth_headers, "Client B")
    job_b = _create_job(client, auth_headers, contact_b["id"])
    _create_estimate(client, auth_headers, job_b["id"])

    resp = client.get(
        f"/api/contacts/{contact_a['id']}/activity", headers=auth_headers
    )
    assert resp.json() == []


def test_activity_empty_for_contact_with_no_activity(
    client, auth_headers, seeded_stages
):
    contact = _create_contact(client, auth_headers)
    resp = client.get(
        f"/api/contacts/{contact['id']}/activity", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_activity_requires_auth(client, auth_headers, seeded_stages):
    contact = _create_contact(client, auth_headers)
    resp = client.get(f"/api/contacts/{contact['id']}/activity")
    assert resp.status_code == 401


def test_activity_404_for_unknown_contact(client, auth_headers):
    resp = client.get("/api/contacts/9999/activity", headers=auth_headers)
    assert resp.status_code == 404
