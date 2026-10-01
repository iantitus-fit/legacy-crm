"""Sprint 17b — SMS endpoint + webhook tests.

All Twilio interactions are mocked.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.models.contact import Contact
from app.models.sms import SmsMessage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def sms_env(monkeypatch):
    monkeypatch.setenv("SMS_ENABLED", "true")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-token-xyz")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+18335550199")
    # Skip signature validation in tests by default — individual tests
    # opt in to signature validation when they want to test it.
    monkeypatch.setenv("TWILIO_WEBHOOK_SKIP_SIGNATURE", "true")
    yield


@pytest.fixture()
def mock_twilio():
    fake_message = MagicMock(sid="SMtest12345", status="queued")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_message
    with patch(
        "app.services.sms_service.get_twilio_client", return_value=fake_client
    ):
        yield fake_client.messages.create


@pytest.fixture(autouse=True)
def _patch_bg_session(db_session, monkeypatch):
    """Background tasks open their own DB session via SessionLocal(). In
    tests we override the SessionLocal factory so those tasks use the same
    in-memory SQLite session as the request handlers."""

    class _SessionShim:
        def __init__(self, session):
            self._session = session

        def __call__(self):
            return self

        def close(self):
            # Don't actually close — the test fixture owns the lifecycle.
            pass

        def __getattr__(self, name):
            return getattr(self._session, name)

    shim = _SessionShim(db_session)
    monkeypatch.setattr("app.database.SessionLocal", shim)
    yield


@pytest.fixture()
def contact(client, auth_headers):
    resp = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={"name": "Alice Carter", "phone": "(765) 555-0181"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture()
def staff_headers(client, auth_headers):
    """Create a staff user and return their auth headers."""
    client.post(
        "/api/employees",
        headers=auth_headers,
        json={
            "full_name": "Staff Worker",
            "email": "staff@legacy.com",
            "password": "password123",
            "role": "staff",
        },
    )
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "staff@legacy.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# POST /api/sms/send
# ---------------------------------------------------------------------------
def test_send_sms_manual(client, auth_headers, contact, sms_env, mock_twilio):
    resp = client.post(
        "/api/sms/send",
        headers=auth_headers,
        json={"contact_id": contact["id"], "body": "Hello there"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["direction"] == "outbound"
    assert data["body"] == "Hello there"
    assert data["to_number"] == "+17655550181"
    assert data["from_number"] == "+18335550199"
    assert data["twilio_sid"] == "SMtest12345"
    assert data["triggered_by"] == "manual"
    assert data["contact_name"] == "Alice Carter"
    mock_twilio.assert_called_once()


def test_send_sms_no_auth(client, contact):
    resp = client.post(
        "/api/sms/send",
        json={"contact_id": contact["id"], "body": "Hi"},
    )
    assert resp.status_code == 401


def test_send_sms_invalid_contact(client, auth_headers, sms_env, mock_twilio):
    resp = client.post(
        "/api/sms/send",
        headers=auth_headers,
        json={"contact_id": 99999, "body": "Hi"},
    )
    assert resp.status_code == 404


def test_send_sms_opted_out(client, auth_headers, db_session, sms_env, mock_twilio):
    c = Contact(name="Opt Out", phone="(765) 555-0166", sms_opt_out=True)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    resp = client.post(
        "/api/sms/send",
        headers=auth_headers,
        json={"contact_id": c.id, "body": "Hi"},
    )
    assert resp.status_code == 400
    assert "opted out" in resp.json()["detail"].lower()


def test_send_sms_no_phone(client, auth_headers, db_session, sms_env, mock_twilio):
    c = Contact(name="No Phone")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    resp = client.post(
        "/api/sms/send",
        headers=auth_headers,
        json={"contact_id": c.id, "body": "Hi"},
    )
    assert resp.status_code == 400
    assert "phone" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /api/contacts/{id}/sms
# ---------------------------------------------------------------------------
def test_get_conversation(client, auth_headers, contact, sms_env, mock_twilio):
    for body in ["First", "Second", "Third"]:
        client.post(
            "/api/sms/send",
            headers=auth_headers,
            json={"contact_id": contact["id"], "body": body},
        )
    resp = client.get(
        f"/api/contacts/{contact['id']}/sms",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["page"] == 1
    # Sorted desc by created_at — most recent first
    bodies = [m["body"] for m in data["items"]]
    assert bodies == ["Third", "Second", "First"]


def test_get_conversation_pagination(
    client, auth_headers, contact, sms_env, mock_twilio
):
    for i in range(5):
        client.post(
            "/api/sms/send",
            headers=auth_headers,
            json={"contact_id": contact["id"], "body": f"msg {i}"},
        )
    resp = client.get(
        f"/api/contacts/{contact['id']}/sms?page=1&per_page=2",
        headers=auth_headers,
    )
    data = resp.json()
    assert data["total"] == 5
    assert data["per_page"] == 2
    assert len(data["items"]) == 2

    resp2 = client.get(
        f"/api/contacts/{contact['id']}/sms?page=3&per_page=2",
        headers=auth_headers,
    )
    data2 = resp2.json()
    assert len(data2["items"]) == 1  # the leftover


def test_get_conversation_no_auth(client, contact):
    resp = client.get(f"/api/contacts/{contact['id']}/sms")
    assert resp.status_code == 401


def test_get_conversation_unknown_contact(client, auth_headers):
    resp = client.get("/api/contacts/99999/sms", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/sms/send-estimate
# ---------------------------------------------------------------------------
def test_send_estimate_link(
    client, auth_headers, contact, db_session, sms_env, mock_twilio, monkeypatch
):
    monkeypatch.setenv("PORTAL_BASE_URL", "https://crm.example.com")
    from app.models.estimate import Estimate
    from app.models.estimate_token import EstimateToken

    estimate = Estimate(
        name="Roof", status="sent", subtotal=0, tax=0, total=0
    )
    db_session.add(estimate)
    db_session.commit()
    db_session.refresh(estimate)
    db_session.add(EstimateToken(estimate_id=estimate.id, token="tok-xyz"))
    db_session.commit()

    resp = client.post(
        "/api/sms/send-estimate",
        headers=auth_headers,
        json={"contact_id": contact["id"], "estimate_id": estimate.id},
    )
    assert resp.status_code == 200
    body = resp.json()["body"]
    assert "https://crm.example.com/portal/estimate/tok-xyz" in body


# ---------------------------------------------------------------------------
# GET/PUT /api/sms/config
# ---------------------------------------------------------------------------
def test_get_config_admin(client, auth_headers):
    resp = client.get("/api/sms/config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "twilio_auth_token_encrypted" not in data
    assert data["auto_respond_new_lead"] is True
    assert "STOP" in data["opt_out_keywords"]


def test_get_config_no_auth(client):
    resp = client.get("/api/sms/config")
    assert resp.status_code == 401


def test_get_config_staff_forbidden(client, staff_headers):
    resp = client.get("/api/sms/config", headers=staff_headers)
    assert resp.status_code == 403


def test_update_config(client, auth_headers):
    resp = client.put(
        "/api/sms/config",
        headers=auth_headers,
        json={
            "auto_respond_new_lead": False,
            "new_lead_template": "Custom template {first_name}",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto_respond_new_lead"] is False
    assert data["new_lead_template"] == "Custom template {first_name}"


def test_update_config_staff_forbidden(client, staff_headers):
    resp = client.put(
        "/api/sms/config",
        headers=staff_headers,
        json={"auto_respond_new_lead": False},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Webhook — inbound
# ---------------------------------------------------------------------------
def test_inbound_webhook_processes_message(
    client, auth_headers, contact, sms_env, db_session
):
    resp = client.post(
        "/api/webhooks/twilio/inbound",
        data={
            "From": "+17655550181",
            "To": "+18335550199",
            "Body": "Hi from the customer",
            "MessageSid": "SMinbound01",
        },
    )
    assert resp.status_code == 200
    assert "<Response/>" in resp.text

    messages = (
        db_session.query(SmsMessage)
        .filter(SmsMessage.contact_id == contact["id"])
        .all()
    )
    assert len(messages) == 1
    assert messages[0].direction == "inbound"
    assert messages[0].body == "Hi from the customer"
    assert messages[0].twilio_sid == "SMinbound01"


def test_inbound_webhook_invalid_signature(client, monkeypatch, contact):
    # Real signature validation enabled, with a known auth token but no header.
    monkeypatch.setenv("SMS_ENABLED", "true")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "real-token")
    monkeypatch.setenv("TWILIO_WEBHOOK_SKIP_SIGNATURE", "false")
    resp = client.post(
        "/api/webhooks/twilio/inbound",
        data={
            "From": "+17655550181",
            "To": "+18335550199",
            "Body": "Hi",
            "MessageSid": "SM-bad",
        },
    )
    assert resp.status_code == 403


def test_inbound_webhook_opt_out_sets_flag(
    client, contact, sms_env, db_session
):
    client.post(
        "/api/webhooks/twilio/inbound",
        data={
            "From": "+17655550181",
            "To": "+18335550199",
            "Body": "STOP",
            "MessageSid": "SM-stop",
        },
    )
    c = db_session.query(Contact).filter(Contact.id == contact["id"]).first()
    assert c.sms_opt_out is True


def test_inbound_webhook_unknown_number_creates_contact(
    client, sms_env, db_session
):
    resp = client.post(
        "/api/webhooks/twilio/inbound",
        data={
            "From": "+13175550199",
            "To": "+18335550199",
            "Body": "Hello",
            "MessageSid": "SM-new",
        },
    )
    assert resp.status_code == 200
    stub = (
        db_session.query(Contact)
        .filter(Contact.phone == "(317) 555-0199")
        .first()
    )
    assert stub is not None
    assert "Unknown" in stub.name


# ---------------------------------------------------------------------------
# Webhook — status callback
# ---------------------------------------------------------------------------
def test_status_webhook_updates_message(
    client, auth_headers, contact, sms_env, mock_twilio, db_session
):
    # Send an outbound message first so we have a SID to look up.
    client.post(
        "/api/sms/send",
        headers=auth_headers,
        json={"contact_id": contact["id"], "body": "Hi"},
    )
    msg = db_session.query(SmsMessage).first()
    assert msg.status == "queued"
    assert msg.twilio_sid == "SMtest12345"

    resp = client.post(
        "/api/webhooks/twilio/status",
        data={
            "MessageSid": "SMtest12345",
            "MessageStatus": "delivered",
        },
    )
    assert resp.status_code == 200
    db_session.refresh(msg)
    assert msg.status == "delivered"


def test_status_webhook_failed_records_error(
    client, auth_headers, contact, sms_env, mock_twilio, db_session
):
    client.post(
        "/api/sms/send",
        headers=auth_headers,
        json={"contact_id": contact["id"], "body": "Hi"},
    )
    client.post(
        "/api/webhooks/twilio/status",
        data={
            "MessageSid": "SMtest12345",
            "MessageStatus": "failed",
            "ErrorMessage": "Invalid number",
        },
    )
    msg = db_session.query(SmsMessage).first()
    db_session.refresh(msg)
    assert msg.status == "failed"
    assert "Invalid number" in (msg.status_detail or "")


def test_status_webhook_unknown_sid_returns_200(client, sms_env):
    """Twilio shouldn't be told to retry just because we don't know a SID."""
    resp = client.post(
        "/api/webhooks/twilio/status",
        data={"MessageSid": "SM-unknown", "MessageStatus": "delivered"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auto-respond wiring on contact creation
# ---------------------------------------------------------------------------
def test_auto_respond_on_lead_creation(
    client, auth_headers, leads_pipeline, sms_env, mock_twilio, db_session
):
    leads_stage = leads_pipeline.stages[0] if leads_pipeline.stages else None
    resp = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={
            "name": "Bob New Lead",
            "phone": "(765) 555-0144",
            "pipeline_id": leads_pipeline.id,
            "stage_id": leads_stage.id if leads_stage else None,
        },
    )
    assert resp.status_code == 201
    contact_id = resp.json()["id"]
    msgs = (
        db_session.query(SmsMessage)
        .filter(SmsMessage.contact_id == contact_id)
        .all()
    )
    assert len(msgs) == 1
    assert msgs[0].triggered_by.startswith("auto_new_lead")


def test_no_auto_respond_for_non_leads_pipeline(
    client, auth_headers, sales_pipeline, sms_env, mock_twilio, db_session
):
    resp = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={
            "name": "Sales Person",
            "phone": "(765) 555-0133",
            "pipeline_id": sales_pipeline.id,
        },
    )
    assert resp.status_code == 201
    contact_id = resp.json()["id"]
    msgs = (
        db_session.query(SmsMessage)
        .filter(SmsMessage.contact_id == contact_id)
        .all()
    )
    assert len(msgs) == 0
    mock_twilio.assert_not_called()


def test_kill_switch_blocks_send(
    client, auth_headers, contact, monkeypatch, mock_twilio
):
    monkeypatch.setenv("SMS_ENABLED", "false")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+18335550199")
    resp = client.post(
        "/api/sms/send",
        headers=auth_headers,
        json={"contact_id": contact["id"], "body": "Hi"},
    )
    # send_sms still returns a record but with status=failed and no Twilio call.
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
    mock_twilio.assert_not_called()


# ---------------------------------------------------------------------------
# Contact response includes sms_opt_out
# ---------------------------------------------------------------------------
def test_contact_response_includes_sms_opt_out(client, auth_headers, contact):
    resp = client.get(f"/api/contacts/{contact['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "sms_opt_out" in data
    assert data["sms_opt_out"] is False
