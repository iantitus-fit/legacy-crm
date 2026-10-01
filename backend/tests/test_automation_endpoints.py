"""Sprint 19b — automation router + trigger-wiring endpoint tests.

Coverage:
- CRUD on sequences, steps, enrollments
- Dashboard + logs
- Per-contact toggle
- Trigger wiring (contact created, estimate sent, inbound SMS reply, job stage change)
- Auth (401 on missing token)

Background-task DB sessions are patched to share the test fixture's in-memory
SQLite. Twilio is fully mocked. SMTP/email is patched per test where needed.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.automation import (
    AutomationEnrollment,
    AutomationLog,
    AutomationSequence,
    AutomationStep,
)
from app.models.contact import Contact
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _patch_bg_session(db_session, monkeypatch):
    """Background tasks open their own SessionLocal(). Shim it so they
    share the test fixture's session."""

    class _SessionShim:
        def __init__(self, session):
            self._session = session

        def __call__(self):
            return self

        def close(self):
            pass

        def __getattr__(self, name):
            return getattr(self._session, name)

    shim = _SessionShim(db_session)
    monkeypatch.setattr("app.database.SessionLocal", shim)
    yield


@pytest.fixture()
def sms_env(monkeypatch):
    monkeypatch.setenv("SMS_ENABLED", "true")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+18335550199")
    monkeypatch.setenv("TWILIO_WEBHOOK_SKIP_SIGNATURE", "true")
    yield


@pytest.fixture()
def mock_twilio():
    fake_msg = MagicMock(sid="SMx", status="queued")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    with patch(
        "app.services.sms_service.get_twilio_client", return_value=fake_client
    ):
        yield fake_client.messages.create


@pytest.fixture()
def contact_payload():
    return {"name": "Alice Carter", "phone": "(765) 555-0181"}


@pytest.fixture()
def contact(client, auth_headers, contact_payload):
    resp = client.post(
        "/api/contacts", headers=auth_headers, json=contact_payload
    )
    assert resp.status_code == 201
    return resp.json()


def _make_sequence_payload(name="Test Seq", trigger="contact_created"):
    return {
        "name": name,
        "description": "test",
        "trigger_type": trigger,
        "trigger_config": {},
        "is_active": True,
        "steps": [
            {
                "channel": "sms",
                "delay_minutes": 0,
                "template_body": "Hi {first_name}",
                "stop_on_reply": True,
                "stop_on_stage_change": True,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Sequences CRUD
# ---------------------------------------------------------------------------
def test_create_sequence_with_inline_steps(client, auth_headers):
    resp = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Test Seq"
    assert body["trigger_type"] == "contact_created"
    assert body["is_active"] is True
    assert body["step_count"] == 1
    assert len(body["steps"]) == 1
    assert body["steps"][0]["step_order"] == 1


def test_create_sequence_requires_auth(client):
    resp = client.post(
        "/api/automations/sequences", json=_make_sequence_payload()
    )
    assert resp.status_code == 401


def test_create_sequence_rejects_duplicate_name(client, auth_headers):
    client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Dup"),
    )
    resp = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Dup"),
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


def test_list_sequences(client, auth_headers):
    client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="A"),
    )
    client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="B"),
    )
    resp = client.get("/api/automations/sequences", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    names = {s["name"] for s in body["items"]}
    assert names == {"A", "B"}


def test_get_sequence_404(client, auth_headers):
    resp = client.get("/api/automations/sequences/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_sequence_partial(client, auth_headers):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Original"),
    )
    seq_id = create.json()["id"]
    resp = client.put(
        f"/api/automations/sequences/{seq_id}",
        headers=auth_headers,
        json={"description": "updated desc"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "updated desc"
    assert resp.json()["name"] == "Original"


def test_toggle_sequence(client, auth_headers):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Toggleable"),
    )
    seq_id = create.json()["id"]
    resp = client.put(
        f"/api/automations/sequences/{seq_id}/toggle", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    resp2 = client.put(
        f"/api/automations/sequences/{seq_id}/toggle", headers=auth_headers
    )
    assert resp2.json()["is_active"] is True


def test_delete_sequence_blocked_by_active_enrollment(
    client, auth_headers, contact
):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Locked"),
    )
    seq_id = create.json()["id"]
    enroll = client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact["id"], "sequence_id": seq_id},
    )
    assert enroll.status_code == 201
    resp = client.delete(
        f"/api/automations/sequences/{seq_id}", headers=auth_headers
    )
    assert resp.status_code == 400
    assert "active enrollment" in resp.json()["detail"].lower()


def test_delete_sequence_soft_deletes_when_clean(client, auth_headers):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Clean"),
    )
    seq_id = create.json()["id"]
    resp = client.delete(
        f"/api/automations/sequences/{seq_id}", headers=auth_headers
    )
    assert resp.status_code == 204
    # Soft delete — sequence still exists but inactive.
    get_resp = client.get(
        f"/api/automations/sequences/{seq_id}", headers=auth_headers
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
def test_add_step_auto_assigns_order(client, auth_headers):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Stepped"),
    )
    seq_id = create.json()["id"]
    resp = client.post(
        f"/api/automations/sequences/{seq_id}/steps",
        headers=auth_headers,
        json={
            "channel": "sms",
            "delay_minutes": 60,
            "template_body": "Step 2 {first_name}",
            "stop_on_reply": True,
            "stop_on_stage_change": True,
            "is_active": True,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["step_order"] == 2


def test_add_step_rejects_bad_channel(client, auth_headers):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="X"),
    )
    seq_id = create.json()["id"]
    resp = client.post(
        f"/api/automations/sequences/{seq_id}/steps",
        headers=auth_headers,
        json={
            "channel": "carrier_pigeon",
            "delay_minutes": 0,
            "template_body": "hi",
        },
    )
    assert resp.status_code == 400


def test_update_step(client, auth_headers):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Y"),
    )
    step_id = create.json()["steps"][0]["id"]
    resp = client.put(
        f"/api/automations/steps/{step_id}",
        headers=auth_headers,
        json={"delay_minutes": 999},
    )
    assert resp.status_code == 200
    assert resp.json()["delay_minutes"] == 999


def test_delete_step(client, auth_headers):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Z"),
    )
    step_id = create.json()["steps"][0]["id"]
    resp = client.delete(
        f"/api/automations/steps/{step_id}", headers=auth_headers
    )
    assert resp.status_code == 204


def test_reorder_steps(client, auth_headers):
    payload = _make_sequence_payload(name="Reorderable")
    payload["steps"] = [
        {"channel": "sms", "delay_minutes": 0, "template_body": "first"},
        {"channel": "sms", "delay_minutes": 60, "template_body": "second"},
    ]
    create = client.post(
        "/api/automations/sequences", headers=auth_headers, json=payload
    )
    body = create.json()
    steps = sorted(body["steps"], key=lambda s: s["step_order"])
    resp = client.put(
        f"/api/automations/sequences/{body['id']}/steps/reorder",
        headers=auth_headers,
        json={
            "items": [
                {"step_id": steps[0]["id"], "step_order": 2},
                {"step_id": steps[1]["id"], "step_order": 1},
            ]
        },
    )
    assert resp.status_code == 200
    new_steps = {s["template_body"]: s["step_order"] for s in resp.json()["steps"]}
    assert new_steps["first"] == 2
    assert new_steps["second"] == 1


# ---------------------------------------------------------------------------
# Enrollments
# ---------------------------------------------------------------------------
def test_manual_enroll_success(client, auth_headers, contact):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Enroll Me"),
    )
    seq_id = create.json()["id"]
    resp = client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact["id"], "sequence_id": seq_id},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["sequence_id"] == seq_id
    assert body["contact_id"] == contact["id"]
    assert body["status"] == "active"


def test_manual_enroll_blocked_by_toggle(client, auth_headers, contact):
    # Disable automations for the contact first.
    client.put(
        f"/api/automations/contacts/{contact['id']}/toggle",
        headers=auth_headers,
        json={"automations_enabled": False},
    )
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Blocked"),
    )
    seq_id = create.json()["id"]
    resp = client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact["id"], "sequence_id": seq_id},
    )
    assert resp.status_code == 400
    assert "automations disabled" in resp.json()["detail"]


def test_manual_enroll_blocked_by_sms_optout(
    client, auth_headers, db_session
):
    opted_out = Contact(
        name="Opt Out", phone="(765) 555-0199", sms_opt_out=True
    )
    db_session.add(opted_out)
    db_session.commit()
    db_session.refresh(opted_out)
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="SMS only"),
    )
    seq_id = create.json()["id"]
    resp = client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": opted_out.id, "sequence_id": seq_id},
    )
    assert resp.status_code == 400
    assert "opted out" in resp.json()["detail"]


def test_list_enrollments_filter_by_status(
    client, auth_headers, contact
):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Filterable"),
    )
    seq_id = create.json()["id"]
    enroll = client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact["id"], "sequence_id": seq_id},
    )
    enrollment_id = enroll.json()["id"]
    client.put(
        f"/api/automations/enrollments/{enrollment_id}/stop",
        headers=auth_headers,
        json={"reason": "test"},
    )
    active = client.get(
        "/api/automations/enrollments?status=active", headers=auth_headers
    )
    assert active.json()["total"] == 0
    stopped = client.get(
        "/api/automations/enrollments?status=stopped_manual",
        headers=auth_headers,
    )
    assert stopped.json()["total"] == 1


def test_stop_enrollment_endpoint(client, auth_headers, contact):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Stop me"),
    )
    seq_id = create.json()["id"]
    enroll = client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact["id"], "sequence_id": seq_id},
    )
    enrollment_id = enroll.json()["id"]
    resp = client.put(
        f"/api/automations/enrollments/{enrollment_id}/stop",
        headers=auth_headers,
        json={"reason": "no thanks"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "stopped_manual"
    assert body["stopped_reason"] == "no thanks"


# ---------------------------------------------------------------------------
# Dashboard + logs
# ---------------------------------------------------------------------------
def test_dashboard_counts(client, auth_headers, contact, db_session):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Dashy"),
    )
    seq_id = create.json()["id"]
    client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact["id"], "sequence_id": seq_id},
    )
    # Seed a sent log row directly so messages_sent_7d is non-zero.
    enrollment = db_session.query(AutomationEnrollment).first()
    step = db_session.query(AutomationStep).first()
    db_session.add(
        AutomationLog(
            enrollment_id=enrollment.id,
            step_id=step.id,
            channel="sms",
            rendered_body="x",
            status="sent",
            sent_at=datetime.now(tz=timezone.utc),
        )
    )
    db_session.commit()

    resp = client.get("/api/automations/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_sequences"] == 1
    assert body["contacts_in_sequences"] == 1
    assert body["messages_sent_7d"] == 1
    assert len(body["recent_activity"]) == 1


def test_logs_endpoint_filterable(client, auth_headers, contact, db_session):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Loggy"),
    )
    seq_id = create.json()["id"]
    client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact["id"], "sequence_id": seq_id},
    )
    enrollment = db_session.query(AutomationEnrollment).first()
    step = db_session.query(AutomationStep).first()
    for status in ("sent", "skipped", "failed"):
        db_session.add(
            AutomationLog(
                enrollment_id=enrollment.id,
                step_id=step.id,
                channel="sms",
                rendered_body=status,
                status=status,
            )
        )
    db_session.commit()
    resp = client.get(
        "/api/automations/logs?status=failed", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["status"] == "failed"


# ---------------------------------------------------------------------------
# Contact toggle
# ---------------------------------------------------------------------------
def test_contact_toggle_flips_field(client, auth_headers, contact, db_session):
    resp = client.put(
        f"/api/automations/contacts/{contact['id']}/toggle",
        headers=auth_headers,
        json={"automations_enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["automations_enabled"] is False
    db_contact = (
        db_session.query(Contact).filter(Contact.id == contact["id"]).first()
    )
    assert db_contact.automations_enabled is False


def test_contact_toggle_unknown_contact(client, auth_headers):
    resp = client.put(
        "/api/automations/contacts/9999/toggle",
        headers=auth_headers,
        json={"automations_enabled": True},
    )
    assert resp.status_code == 404


def test_contact_enrollments_listing(client, auth_headers, contact):
    create = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="ContactListing"),
    )
    seq_id = create.json()["id"]
    client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact["id"], "sequence_id": seq_id},
    )
    resp = client.get(
        f"/api/automations/contacts/{contact['id']}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["sequence_id"] == seq_id


# ---------------------------------------------------------------------------
# Trigger wiring — contact_created hook from POST /api/contacts
# ---------------------------------------------------------------------------
def test_contact_created_trigger_enrolls(client, auth_headers, db_session):
    # Pre-create a contact_created sequence.
    seq_resp = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Welcome", trigger="contact_created"),
    )
    seq_id = seq_resp.json()["id"]

    contact_resp = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={"name": "New Lead", "phone": "(765) 555-0144"},
    )
    contact_id = contact_resp.json()["id"]

    # Background task should have enrolled the contact.
    enrollments = (
        db_session.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.sequence_id == seq_id,
            AutomationEnrollment.contact_id == contact_id,
        )
        .all()
    )
    assert len(enrollments) == 1
    assert enrollments[0].status == "active"


# ---------------------------------------------------------------------------
# Trigger wiring — pipeline_stage_change via PATCH /api/jobs/{id}/stage
# ---------------------------------------------------------------------------
def test_stage_change_trigger(
    client, auth_headers, db_session, seeded_stages
):
    """Moving a job to a stage should fire enrollments matching that move."""
    from app.models.job import Job

    sales_pipeline = (
        db_session.query(Pipeline).filter(Pipeline.slug == "sales").first()
    )
    stages = (
        db_session.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == sales_pipeline.id)
        .order_by(PipelineStage.sort_order)
        .all()
    )
    contact = Contact(name="Mover", phone="(765) 555-0123")
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    job = Job(
        contact_id=contact.id,
        pipeline_id=sales_pipeline.id,
        stage_id=stages[0].id,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    target_stage = stages[1]
    seq_resp = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json={
            "name": "Stage Match",
            "trigger_type": "pipeline_stage_change",
            "trigger_config": {
                "pipeline_slug": "sales",
                "to_stage_id": target_stage.id,
            },
            "steps": [
                {
                    "channel": "sms",
                    "delay_minutes": 0,
                    "template_body": "stage hi",
                }
            ],
        },
    )
    seq_id = seq_resp.json()["id"]

    resp = client.patch(
        f"/api/jobs/{job.id}/stage",
        headers=auth_headers,
        json={"stage_id": target_stage.id},
    )
    assert resp.status_code == 200

    enrollments = (
        db_session.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.contact_id == contact.id,
            AutomationEnrollment.sequence_id == seq_id,
        )
        .all()
    )
    assert len(enrollments) == 1


def test_stage_change_stops_active_enrollment(
    client, auth_headers, db_session, seeded_stages
):
    """An active sequence with stop_on_stage_change should stop after a move."""
    from app.models.job import Job

    sales_pipeline = (
        db_session.query(Pipeline).filter(Pipeline.slug == "sales").first()
    )
    stages = (
        db_session.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == sales_pipeline.id)
        .order_by(PipelineStage.sort_order)
        .all()
    )
    contact = Contact(name="Stopper", phone="(765) 555-0188")
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    seq_resp = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Will Stop"),
    )
    seq_id = seq_resp.json()["id"]
    client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact.id, "sequence_id": seq_id},
    )

    job = Job(
        contact_id=contact.id,
        pipeline_id=sales_pipeline.id,
        stage_id=stages[0].id,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    resp = client.patch(
        f"/api/jobs/{job.id}/stage",
        headers=auth_headers,
        json={"stage_id": stages[1].id},
    )
    assert resp.status_code == 200

    enrollment = (
        db_session.query(AutomationEnrollment)
        .filter(AutomationEnrollment.contact_id == contact.id)
        .first()
    )
    assert enrollment.status == "stopped_stage_change"


# ---------------------------------------------------------------------------
# Trigger wiring — inbound SMS reply stop via webhook
# ---------------------------------------------------------------------------
def test_inbound_sms_stops_active_enrollment(
    client, auth_headers, contact, sms_env, db_session
):
    seq_resp = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Reply Stop"),
    )
    seq_id = seq_resp.json()["id"]
    client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact["id"], "sequence_id": seq_id},
    )

    resp = client.post(
        "/api/webhooks/twilio/inbound",
        data={
            "From": "+17655550181",
            "To": "+18335550199",
            "Body": "thanks for reaching out",
            "MessageSid": "SMin01",
        },
    )
    assert resp.status_code == 200

    enrollment = (
        db_session.query(AutomationEnrollment)
        .filter(AutomationEnrollment.contact_id == contact["id"])
        .first()
    )
    assert enrollment.status == "stopped_reply"


def test_inbound_sms_stop_keyword_triggers_optout_stop(
    client, auth_headers, db_session, sms_env
):
    contact = Contact(name="Stop Reply", phone="(765) 555-0177")
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    # Sequence with stop_on_reply=False so the only path that can stop it
    # is the opt-out hook.
    seq_resp = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json={
            "name": "Opt Out Stops",
            "trigger_type": "manual",
            "steps": [
                {
                    "channel": "sms",
                    "delay_minutes": 0,
                    "template_body": "hi",
                    "stop_on_reply": False,
                    "stop_on_stage_change": False,
                }
            ],
        },
    )
    seq_id = seq_resp.json()["id"]
    client.post(
        "/api/automations/enroll",
        headers=auth_headers,
        json={"contact_id": contact.id, "sequence_id": seq_id},
    )

    resp = client.post(
        "/api/webhooks/twilio/inbound",
        data={
            "From": "+17655550177",
            "To": "+18335550199",
            "Body": "STOP",
            "MessageSid": "SMin02",
        },
    )
    assert resp.status_code == 200

    enrollment = (
        db_session.query(AutomationEnrollment)
        .filter(AutomationEnrollment.contact_id == contact.id)
        .first()
    )
    assert enrollment.status == "stopped_optout"


# ---------------------------------------------------------------------------
# Trigger wiring — estimate_sent hook
# ---------------------------------------------------------------------------
def test_estimate_sent_trigger(
    client, auth_headers, db_session, seeded_stages, monkeypatch
):
    """POST /api/estimates/{id}/send should enroll the contact in any
    estimate_sent sequence."""
    from app.models.estimate import Estimate
    from app.models.job import Job

    monkeypatch.setattr(
        "app.routers.estimate_email.send_email", lambda **kw: True
    )

    contact = Contact(
        name="Buyer", phone="(765) 555-0150", email="buyer@example.com"
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    sales_pipeline = (
        db_session.query(Pipeline).filter(Pipeline.slug == "sales").first()
    )
    first_stage = (
        db_session.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == sales_pipeline.id)
        .order_by(PipelineStage.sort_order)
        .first()
    )
    job = Job(
        contact_id=contact.id,
        pipeline_id=sales_pipeline.id,
        stage_id=first_stage.id,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    estimate = Estimate(
        job_id=job.id,
        name="Roof",
        status="draft",
        subtotal=0,
        tax=0,
        total=0,
    )
    db_session.add(estimate)
    db_session.commit()
    db_session.refresh(estimate)

    seq_resp = client.post(
        "/api/automations/sequences",
        headers=auth_headers,
        json=_make_sequence_payload(name="Quote Followup", trigger="estimate_sent"),
    )
    seq_id = seq_resp.json()["id"]

    resp = client.post(
        f"/api/estimates/{estimate.id}/send",
        headers=auth_headers,
        json={"to_email": "buyer@example.com"},
    )
    assert resp.status_code == 200

    enrollments = (
        db_session.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.contact_id == contact.id,
            AutomationEnrollment.sequence_id == seq_id,
        )
        .all()
    )
    assert len(enrollments) == 1
