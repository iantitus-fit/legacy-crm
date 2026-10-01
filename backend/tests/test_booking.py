"""Sprint 20c — public booking form."""
from unittest.mock import patch

import pytest

from app.models.contact import Contact
from app.models.lead import Lead
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.routers import booking as booking_module


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """The IP rate limiter is module-level; clear it between tests."""
    booking_module._reset_rate_limits_for_tests()
    yield
    booking_module._reset_rate_limits_for_tests()


def _base_payload(**overrides):
    body = {
        "first_name": "Jane",
        "last_name": "Doe",
        "phone": "555-0101",
        "email": "jane@example.com",
        "address": "100 Main St",
        "city": "Kokomo",
        "zip": "46901",
        "service_type": "Roofing",
        "message": "Need a new roof, hail damage from last week.",
    }
    body.update(overrides)
    return body


# --- Successful submission ------------------------------------------------


def test_book_creates_contact_and_lead(client, seeded_stages, db_session):
    resp = client.post("/api/public/book", json=_base_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["contact_id"]
    assert body["lead_id"]

    contact = db_session.query(Contact).filter(Contact.id == body["contact_id"]).first()
    assert contact.name == "Jane Doe"
    assert contact.phone == "555-0101"
    assert contact.email == "jane@example.com"
    assert contact.state == "IN"  # CLAUDE.md rule 5

    lead = db_session.query(Lead).filter(Lead.id == body["lead_id"]).first()
    assert lead.contact_id == contact.id
    assert "Roofing" in (lead.description or "")
    assert "hail damage" in (lead.description or "")


def test_book_places_contact_in_leads_pipeline_first_stage(
    client, seeded_stages, db_session
):
    resp = client.post("/api/public/book", json=_base_payload())
    assert resp.status_code == 201
    body = resp.json()
    contact = db_session.query(Contact).filter(Contact.id == body["contact_id"]).first()

    leads_pipeline = db_session.query(Pipeline).filter(Pipeline.slug == "leads").first()
    first_stage = (
        db_session.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == leads_pipeline.id)
        .order_by(PipelineStage.sort_order)
        .first()
    )
    assert contact.pipeline_id == leads_pipeline.id
    assert contact.stage_id == first_stage.id


def test_book_no_auth_required(client, seeded_stages):
    """No Authorization header — should still succeed."""
    resp = client.post("/api/public/book", json=_base_payload())
    assert resp.status_code == 201


# --- Lead source ----------------------------------------------------------


def test_lead_source_from_form_overrides_default(client, seeded_stages, db_session):
    payload = _base_payload(lead_source="Google LSA")
    resp = client.post("/api/public/book", json=payload)
    contact = db_session.query(Contact).filter(
        Contact.id == resp.json()["contact_id"]
    ).first()
    assert contact.lead_source == "Google LSA"


def test_lead_source_defaults_to_website(client, seeded_stages, db_session):
    payload = _base_payload()
    payload.pop("email", None)  # also exercise optional-field handling
    resp = client.post("/api/public/book", json=payload)
    contact = db_session.query(Contact).filter(
        Contact.id == resp.json()["contact_id"]
    ).first()
    assert contact.lead_source == "Website"


# --- Duplicate handling ---------------------------------------------------


def test_returning_contact_matched_by_phone(client, seeded_stages, db_session):
    first = client.post("/api/public/book", json=_base_payload()).json()
    # Same phone, different email
    second = client.post(
        "/api/public/book",
        json=_base_payload(email="jane.new@example.com"),
    ).json()
    assert first["contact_id"] == second["contact_id"]
    # New lead row each time so the board shows the new inquiry
    assert first["lead_id"] != second["lead_id"]


def test_returning_contact_matched_by_email(client, seeded_stages, db_session):
    client.post("/api/public/book", json=_base_payload())
    second = client.post(
        "/api/public/book",
        json=_base_payload(phone="555-9999"),  # different phone
    ).json()
    contact = db_session.query(Contact).filter(
        Contact.id == second["contact_id"]
    ).first()
    # Original phone stays — we don't overwrite
    assert contact.phone == "555-0101"


def test_returning_contact_fills_in_missing_fields(
    client, seeded_stages, db_session
):
    payload = _base_payload()
    payload.pop("email", None)
    payload.pop("address", None)
    first = client.post("/api/public/book", json=payload).json()
    # Second submission supplies email + address
    client.post(
        "/api/public/book",
        json=_base_payload(),  # has email + address
    )
    contact = db_session.query(Contact).filter(
        Contact.id == first["contact_id"]
    ).first()
    assert contact.email == "jane@example.com"
    assert contact.address == "100 Main St"


# --- Validation -----------------------------------------------------------


def test_missing_first_name_rejected(client, seeded_stages):
    payload = _base_payload()
    payload.pop("first_name")
    resp = client.post("/api/public/book", json=payload)
    assert resp.status_code == 422


def test_missing_phone_rejected(client, seeded_stages):
    payload = _base_payload()
    payload.pop("phone")
    resp = client.post("/api/public/book", json=payload)
    assert resp.status_code == 422


def test_invalid_service_type_rejected(client, seeded_stages):
    resp = client.post(
        "/api/public/book",
        json=_base_payload(service_type="Plumbing"),
    )
    assert resp.status_code == 422


def test_email_optional(client, seeded_stages):
    payload = _base_payload()
    payload.pop("email")
    resp = client.post("/api/public/book", json=payload)
    assert resp.status_code == 201


# --- Honeypot -------------------------------------------------------------


def test_honeypot_silently_accepts(client, seeded_stages, db_session):
    """Bot fills the hidden company_website field — we 200 silently and
    create nothing, so the bot can't detect the rejection."""
    before = db_session.query(Contact).count()
    resp = client.post(
        "/api/public/book",
        json=_base_payload(company_website="http://bot.example.com"),
    )
    assert resp.status_code == 201
    assert resp.json()["success"] is True
    assert "contact_id" not in resp.json()
    assert db_session.query(Contact).count() == before


# --- Rate limiting --------------------------------------------------------


def test_rate_limit_blocks_after_five(client, seeded_stages):
    for i in range(5):
        resp = client.post(
            "/api/public/book",
            json=_base_payload(phone=f"555-010{i}"),
        )
        assert resp.status_code == 201, f"submission {i + 1} unexpectedly failed"

    resp = client.post(
        "/api/public/book", json=_base_payload(phone="555-9999")
    )
    assert resp.status_code == 429
    assert "Too many" in resp.json()["detail"]


# --- Background triggers --------------------------------------------------


def test_on_contact_created_fires_for_new_contact(client, seeded_stages):
    with patch(
        "app.routers.booking._on_contact_created_task"
    ) as mock_task:
        resp = client.post("/api/public/book", json=_base_payload())
    assert resp.status_code == 201
    mock_task.assert_called_once()
    # First positional arg is the contact_id
    assert mock_task.call_args.args[0] == resp.json()["contact_id"]


def test_on_contact_created_skipped_for_returning_contact(
    client, seeded_stages
):
    client.post("/api/public/book", json=_base_payload())
    with patch(
        "app.routers.booking._on_contact_created_task"
    ) as mock_task:
        client.post("/api/public/book", json=_base_payload())
    mock_task.assert_not_called()


def test_auto_respond_sms_fires(client, seeded_stages):
    with patch(
        "app.routers.booking._auto_respond_new_lead_task"
    ) as mock_task:
        resp = client.post("/api/public/book", json=_base_payload())
    assert resp.status_code == 201
    mock_task.assert_called_once()


def test_company_notification_fires(client, seeded_stages):
    with patch(
        "app.routers.booking._send_company_notification_task"
    ) as mock_task:
        resp = client.post("/api/public/book", json=_base_payload())
    assert resp.status_code == 201
    mock_task.assert_called_once()
    args = mock_task.call_args.args
    assert args[0] == resp.json()["contact_id"]
    # Payload dict passed through
    assert args[1]["service_type"] == "Roofing"


def test_honeypot_skips_all_triggers(client, seeded_stages):
    with patch(
        "app.routers.booking._on_contact_created_task"
    ) as mock_create, patch(
        "app.routers.booking._auto_respond_new_lead_task"
    ) as mock_sms, patch(
        "app.routers.booking._send_company_notification_task"
    ) as mock_notify:
        resp = client.post(
            "/api/public/book",
            json=_base_payload(company_website="bait"),
        )
    assert resp.status_code == 201
    mock_create.assert_not_called()
    mock_sms.assert_not_called()
    mock_notify.assert_not_called()
