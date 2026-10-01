"""Sprint 19a — automation engine service tests.

These tests cover the data model, service layer, and trigger handlers.
All Twilio + SMTP calls are mocked. The scheduler entry point
``process_pending_steps`` is exercised directly with a controlled clock.
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
from app.services import automation_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def sms_env(monkeypatch):
    monkeypatch.setenv("SMS_ENABLED", "true")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+18335550199")


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
def contact(db_session):
    c = Contact(
        name="Alice Carter",
        phone="(765) 555-0181",
        email="alice@example.com",
        company="Acme",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture()
def no_phone_contact(db_session):
    c = Contact(name="No Phone", email="np@example.com")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture()
def opted_out_contact(db_session):
    c = Contact(
        name="Bob Optout",
        phone="(765) 555-0199",
        email="bob@example.com",
        sms_opt_out=True,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture()
def disabled_contact(db_session):
    c = Contact(
        name="Carla Disabled",
        phone="(765) 555-0144",
        automations_enabled=False,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def _seq(
    db,
    *,
    name="Test Sequence",
    trigger_type="contact_created",
    trigger_config=None,
    is_active=True,
    steps=None,
):
    seq = AutomationSequence(
        name=name,
        trigger_type=trigger_type,
        trigger_config=trigger_config or {},
        is_active=is_active,
    )
    db.add(seq)
    db.commit()
    db.refresh(seq)
    for s in steps or []:
        db.add(AutomationStep(sequence_id=seq.id, **s))
    db.commit()
    db.refresh(seq)
    return seq


def _basic_sms_step(order=1, body="Hi {first_name}", delay=0, **overrides):
    base = dict(
        step_order=order,
        channel="sms",
        delay_minutes=delay,
        template_body=body,
    )
    base.update(overrides)
    return base


def _basic_email_step(order=1, subject="Hi {first_name}", body="<p>Hi</p>", delay=0):
    return dict(
        step_order=order,
        channel="email",
        delay_minutes=delay,
        template_subject=subject,
        template_body=body,
    )


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------
def test_enroll_contact_success(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step(delay=0)])
    result = automation_service.enroll_contact(db_session, contact.id, seq.id)
    assert result.enrollment is not None
    assert result.enrollment.status == "active"
    assert result.enrollment.current_step_order == 1
    assert result.enrollment.next_step_at is not None


def test_enroll_contact_unknown_contact(db_session):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    result = automation_service.enroll_contact(db_session, 9999, seq.id)
    assert result.enrollment is None
    assert "not found" in result.reason


def test_enroll_contact_unknown_sequence(db_session, contact):
    result = automation_service.enroll_contact(db_session, contact.id, 9999)
    assert result.enrollment is None
    assert "not found" in result.reason


def test_enroll_contact_blocked_by_automations_disabled(
    db_session, disabled_contact
):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    result = automation_service.enroll_contact(
        db_session, disabled_contact.id, seq.id
    )
    assert result.enrollment is None
    assert "automations disabled" in result.reason


def test_enroll_contact_blocked_by_sms_opt_out(db_session, opted_out_contact):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    result = automation_service.enroll_contact(
        db_session, opted_out_contact.id, seq.id
    )
    assert result.enrollment is None
    assert "opted out" in result.reason


def test_enroll_contact_email_only_seq_allows_opt_out(
    db_session, opted_out_contact
):
    seq = _seq(db_session, steps=[_basic_email_step()])
    result = automation_service.enroll_contact(
        db_session, opted_out_contact.id, seq.id
    )
    assert result.enrollment is not None


def test_enroll_contact_blocked_by_inactive_sequence(db_session, contact):
    seq = _seq(
        db_session,
        is_active=False,
        steps=[_basic_sms_step()],
    )
    result = automation_service.enroll_contact(db_session, contact.id, seq.id)
    assert result.enrollment is None
    assert "inactive" in result.reason


def test_enroll_contact_blocked_when_no_active_steps(db_session, contact):
    seq = _seq(
        db_session,
        steps=[_basic_sms_step(is_active=False)],
    )
    result = automation_service.enroll_contact(db_session, contact.id, seq.id)
    assert result.enrollment is None
    assert "no active steps" in result.reason


def test_enroll_contact_prevents_duplicate(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    first = automation_service.enroll_contact(db_session, contact.id, seq.id)
    assert first.enrollment is not None
    second = automation_service.enroll_contact(db_session, contact.id, seq.id)
    assert second.enrollment is None
    assert "already" in second.reason


def test_enroll_contact_after_stop_blocked_by_unique_constraint(
    db_session, contact
):
    # The spec's unique (sequence_id, contact_id) constraint prevents
    # re-enrollment even after a stop. enroll_contact catches the resulting
    # IntegrityError and returns a clean reason instead of bubbling up.
    seq = _seq(db_session, steps=[_basic_sms_step()])
    first = automation_service.enroll_contact(db_session, contact.id, seq.id)
    automation_service.stop_enrollment(
        db_session, first.enrollment.id, "manual"
    )
    second = automation_service.enroll_contact(db_session, contact.id, seq.id)
    assert second.enrollment is None
    assert "already" in (second.reason or "").lower()


# ---------------------------------------------------------------------------
# Stop enrollment
# ---------------------------------------------------------------------------
def test_stop_enrollment_reply(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    out = automation_service.stop_enrollment(
        db_session, enrollment.id, "reply", "contact replied STOP"
    )
    assert out.status == "stopped_reply"
    assert out.stopped_at is not None
    assert out.stopped_reason == "contact replied STOP"
    assert out.next_step_at is None


def test_stop_enrollment_stage_change(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    out = automation_service.stop_enrollment(
        db_session, enrollment.id, "stage_change"
    )
    assert out.status == "stopped_stage_change"


def test_stop_enrollment_manual(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    out = automation_service.stop_enrollment(db_session, enrollment.id, "manual")
    assert out.status == "stopped_manual"


def test_stop_enrollment_optout(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    out = automation_service.stop_enrollment(db_session, enrollment.id, "optout")
    assert out.status == "stopped_optout"


def test_stop_enrollment_unknown_id(db_session):
    assert automation_service.stop_enrollment(db_session, 9999, "manual") is None


def test_stop_enrollment_idempotent(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    first = automation_service.stop_enrollment(
        db_session, enrollment.id, "manual"
    )
    second = automation_service.stop_enrollment(
        db_session, enrollment.id, "reply"
    )
    # Second call should not change status — already stopped.
    assert second.status == first.status == "stopped_manual"


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------
def test_render_template_all_tokens(db_session, contact):
    out = automation_service.render_template(
        "Hi {first_name} {last_name}, {company_name} — call {company_phone}",
        contact,
    )
    assert "Hi Alice Carter" in out
    assert "Acme" in out
    # company_phone falls back to default env
    assert "(" in out  # phone formatting


def test_render_template_missing_token_graceful(db_session, contact):
    out = automation_service.render_template(
        "Hi {first_name}, total is {estimate_total}", contact
    )
    assert out == "Hi Alice, total is "


def test_render_template_overrides_win(db_session, contact):
    out = automation_service.render_template(
        "Hi {first_name} from {rep_name}",
        contact,
        rep_name="Dale",
    )
    assert out == "Hi Alice from Dale"


def test_render_template_estimate_tokens(db_session, contact, monkeypatch):
    monkeypatch.setenv("PORTAL_BASE_URL", "https://crm.example.com")

    fake_user = MagicMock(full_name="Dale Owner")
    fake_token = MagicMock(token="tok-abc", created_at=datetime.now())
    fake_estimate = MagicMock(
        assigned_to=fake_user,
        work_type="roofing",
        total=12345.67,
        tokens=[fake_token],
    )
    out = automation_service.render_template(
        "Hi {first_name}, rep {rep_name}, service {service_type}, "
        "amount {estimate_total}, link {estimate_link}",
        contact,
        estimate=fake_estimate,
    )
    assert "rep Dale Owner" in out
    assert "service Roofing" in out
    assert "amount $12,345.67" in out
    assert "https://crm.example.com/portal/estimate/tok-abc" in out


def test_render_template_handles_none_template():
    assert automation_service.render_template(None) == ""
    assert automation_service.render_template("") == ""


def test_render_template_no_contact():
    out = automation_service.render_template("Hi {first_name}!")
    assert out == "Hi !"


# ---------------------------------------------------------------------------
# Step execution via process_pending_steps
# ---------------------------------------------------------------------------
def _enroll_due_now(db, contact_id, seq_id):
    enrollment = automation_service.enroll_contact(
        db, contact_id, seq_id
    ).enrollment
    # Force the next-step deadline into the past so process_pending_steps picks it up.
    enrollment.next_step_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    db.commit()
    return enrollment


def test_process_pending_sends_sms(db_session, contact, sms_env, mock_twilio):
    seq = _seq(db_session, steps=[_basic_sms_step(body="Hello {first_name}")])
    enrollment = _enroll_due_now(db_session, contact.id, seq.id)

    logs = automation_service.process_pending_steps(db_session)
    assert len(logs) == 1
    log = logs[0]
    assert log.status == "sent"
    assert log.channel == "sms"
    assert log.rendered_body == "Hello Alice"
    mock_twilio.assert_called_once()

    db_session.refresh(enrollment)
    assert enrollment.status == "completed"  # only one step
    assert enrollment.completed_at is not None


def test_process_pending_skips_when_sms_disabled(
    db_session, contact, monkeypatch
):
    monkeypatch.setenv("SMS_ENABLED", "false")
    seq = _seq(db_session, steps=[_basic_sms_step()])
    _enroll_due_now(db_session, contact.id, seq.id)
    logs = automation_service.process_pending_steps(db_session)
    assert len(logs) == 1
    assert logs[0].status == "skipped"
    assert "SMS_ENABLED" in (logs[0].error_message or "")


def test_process_pending_skips_when_no_phone(db_session, no_phone_contact, sms_env):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    _enroll_due_now(db_session, no_phone_contact.id, seq.id)
    logs = automation_service.process_pending_steps(db_session)
    assert logs[0].status == "skipped"
    assert "phone" in (logs[0].error_message or "")


def test_process_pending_skips_opt_out_mid_flight(
    db_session, contact, sms_env, mock_twilio
):
    seq = _seq(
        db_session,
        steps=[
            _basic_sms_step(order=1, body="step 1"),
            _basic_sms_step(order=2, body="step 2", delay=0),
        ],
    )
    enrollment = _enroll_due_now(db_session, contact.id, seq.id)
    automation_service.process_pending_steps(db_session)
    # Now contact opts out mid-sequence; second step should skip.
    contact.sms_opt_out = True
    db_session.commit()
    db_session.refresh(enrollment)
    enrollment.next_step_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    logs = automation_service.process_pending_steps(db_session)
    assert logs[-1].status == "skipped"


def test_process_pending_sends_email(db_session, contact):
    seq = _seq(
        db_session,
        steps=[
            _basic_email_step(
                subject="Hi {first_name}",
                body="<p>Hello {first_name}</p>",
            )
        ],
    )
    _enroll_due_now(db_session, contact.id, seq.id)
    with patch(
        "app.services.email_service.send_email", return_value=True
    ) as mock_email:
        logs = automation_service.process_pending_steps(db_session)
    assert logs[0].status == "sent"
    assert logs[0].rendered_subject == "Hi Alice"
    mock_email.assert_called_once()
    args, kwargs = mock_email.call_args
    assert kwargs["to_email"] == "alice@example.com"
    assert kwargs["subject"] == "Hi Alice"
    assert "Hello Alice" in kwargs["html_body"]


def test_process_pending_email_skipped_no_email(db_session):
    contact = Contact(name="Phone Only", phone="(765) 555-0111")
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    seq = _seq(db_session, steps=[_basic_email_step()])
    _enroll_due_now(db_session, contact.id, seq.id)
    logs = automation_service.process_pending_steps(db_session)
    assert logs[0].status == "skipped"
    assert "email" in (logs[0].error_message or "")


def test_process_pending_email_failure_recorded(db_session, contact):
    seq = _seq(db_session, steps=[_basic_email_step()])
    _enroll_due_now(db_session, contact.id, seq.id)
    with patch(
        "app.services.email_service.send_email",
        side_effect=RuntimeError("SMTP down"),
    ):
        logs = automation_service.process_pending_steps(db_session)
    assert logs[0].status == "failed"
    assert "SMTP down" in (logs[0].error_message or "")


def test_process_pending_advances_through_steps(
    db_session, contact, sms_env, mock_twilio
):
    seq = _seq(
        db_session,
        steps=[
            _basic_sms_step(order=1, body="one"),
            _basic_sms_step(order=2, body="two", delay=10),
            _basic_sms_step(order=3, body="three", delay=10),
        ],
    )
    enrollment = _enroll_due_now(db_session, contact.id, seq.id)

    # First pass — step 1 fires; step 2 scheduled 10 min from now.
    automation_service.process_pending_steps(db_session)
    db_session.refresh(enrollment)
    assert enrollment.current_step_order == 2
    assert enrollment.status == "active"

    # Time hasn't advanced — nothing should fire.
    logs = automation_service.process_pending_steps(db_session)
    assert logs == []

    # Force step 2 due, fire, and check that step 3 is queued.
    enrollment.next_step_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    automation_service.process_pending_steps(db_session)
    db_session.refresh(enrollment)
    assert enrollment.current_step_order == 3

    enrollment.next_step_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    automation_service.process_pending_steps(db_session)
    db_session.refresh(enrollment)
    assert enrollment.status == "completed"
    assert enrollment.completed_at is not None


def test_process_pending_respects_inactive_sequence(
    db_session, contact, sms_env, mock_twilio
):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    enrollment = _enroll_due_now(db_session, contact.id, seq.id)
    seq.is_active = False
    db_session.commit()
    logs = automation_service.process_pending_steps(db_session)
    assert logs == []
    db_session.refresh(enrollment)
    assert enrollment.status == "active"  # paused, not stopped


def test_process_pending_stops_if_contact_disabled_mid_flight(
    db_session, contact, sms_env, mock_twilio
):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    enrollment = _enroll_due_now(db_session, contact.id, seq.id)
    contact.automations_enabled = False
    db_session.commit()
    automation_service.process_pending_steps(db_session)
    db_session.refresh(enrollment)
    assert enrollment.status == "stopped_manual"


def test_process_pending_skips_future_steps(
    db_session, contact, sms_env, mock_twilio
):
    seq = _seq(db_session, steps=[_basic_sms_step(delay=60)])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    # Don't force the deadline into the past.
    logs = automation_service.process_pending_steps(db_session)
    assert logs == []
    db_session.refresh(enrollment)
    assert enrollment.status == "active"


def test_process_pending_handles_deactivated_step(
    db_session, contact, sms_env, mock_twilio
):
    seq = _seq(
        db_session,
        steps=[
            _basic_sms_step(order=1, body="one"),
            _basic_sms_step(order=2, body="two"),
        ],
    )
    enrollment = _enroll_due_now(db_session, contact.id, seq.id)
    # Deactivate step 1 between enrollment and processing.
    step1 = (
        db_session.query(AutomationStep)
        .filter(AutomationStep.sequence_id == seq.id, AutomationStep.step_order == 1)
        .first()
    )
    step1.is_active = False
    db_session.commit()
    logs = automation_service.process_pending_steps(db_session)
    # Engine should skip to step 2.
    assert len(logs) == 1
    assert logs[0].rendered_body == "two"


# ---------------------------------------------------------------------------
# Trigger handlers
# ---------------------------------------------------------------------------
def test_on_contact_created_enrolls(db_session, contact):
    seq = _seq(
        db_session,
        trigger_type="contact_created",
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_contact_created(db_session, contact.id)
    assert len(enrolled) == 1
    assert enrolled[0].sequence_id == seq.id


def test_on_contact_created_ignores_other_triggers(db_session, contact):
    _seq(
        db_session,
        trigger_type="estimate_sent",
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_contact_created(db_session, contact.id)
    assert enrolled == []


def test_on_contact_created_skips_inactive_sequence(db_session, contact):
    _seq(
        db_session,
        trigger_type="contact_created",
        is_active=False,
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_contact_created(db_session, contact.id)
    assert enrolled == []


def test_on_estimate_sent_enrolls(db_session, contact):
    seq = _seq(
        db_session,
        trigger_type="estimate_sent",
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_estimate_sent(db_session, contact.id, 1)
    assert len(enrolled) == 1
    assert enrolled[0].sequence_id == seq.id


def test_on_pipeline_stage_change_matches_stage(db_session, contact):
    seq = _seq(
        db_session,
        trigger_type="pipeline_stage_change",
        trigger_config={"pipeline_slug": "sales", "to_stage_id": 7},
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_pipeline_stage_change(
        db_session, contact.id, "sales", from_stage_id=4, to_stage_id=7
    )
    assert len(enrolled) == 1
    assert enrolled[0].sequence_id == seq.id


def test_on_pipeline_stage_change_ignores_wrong_pipeline(db_session, contact):
    _seq(
        db_session,
        trigger_type="pipeline_stage_change",
        trigger_config={"pipeline_slug": "sales", "to_stage_id": 7},
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_pipeline_stage_change(
        db_session, contact.id, "leads", from_stage_id=4, to_stage_id=7
    )
    assert enrolled == []


def test_on_pipeline_stage_change_ignores_wrong_stage(db_session, contact):
    _seq(
        db_session,
        trigger_type="pipeline_stage_change",
        trigger_config={"pipeline_slug": "sales", "to_stage_id": 7},
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_pipeline_stage_change(
        db_session, contact.id, "sales", from_stage_id=4, to_stage_id=8
    )
    assert enrolled == []


def test_on_pipeline_stage_change_no_target_matches_all(db_session, contact):
    seq = _seq(
        db_session,
        trigger_type="pipeline_stage_change",
        trigger_config={"pipeline_slug": "sales"},
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_pipeline_stage_change(
        db_session, contact.id, "sales", from_stage_id=2, to_stage_id=5
    )
    assert len(enrolled) == 1
    assert enrolled[0].sequence_id == seq.id


def test_on_pipeline_stage_change_also_fires_job_completed(db_session, contact):
    job_seq = _seq(
        db_session,
        trigger_type="job_completed",
        trigger_config={"pipeline_slug": "jobs", "to_stage_id": 12},
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_pipeline_stage_change(
        db_session, contact.id, "jobs", from_stage_id=11, to_stage_id=12
    )
    assert any(e.sequence_id == job_seq.id for e in enrolled)


def test_on_job_completed_enrolls(db_session, contact):
    seq = _seq(
        db_session,
        trigger_type="job_completed",
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_job_completed(db_session, contact.id, job_id=1)
    assert len(enrolled) == 1
    assert enrolled[0].sequence_id == seq.id


def test_trigger_respects_automations_disabled(db_session, disabled_contact):
    _seq(
        db_session,
        trigger_type="contact_created",
        steps=[_basic_sms_step()],
    )
    enrolled = automation_service.on_contact_created(
        db_session, disabled_contact.id
    )
    assert enrolled == []


# ---------------------------------------------------------------------------
# Stop-condition checks
# ---------------------------------------------------------------------------
def test_check_reply_stop_stops_active_enrollment(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step(stop_on_reply=True)])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    stopped = automation_service.check_reply_stop(db_session, contact.id)
    assert len(stopped) == 1
    db_session.refresh(enrollment)
    assert enrollment.status == "stopped_reply"


def test_check_reply_stop_respects_flag(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step(stop_on_reply=False)])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    stopped = automation_service.check_reply_stop(db_session, contact.id)
    assert stopped == []
    db_session.refresh(enrollment)
    assert enrollment.status == "active"


def test_check_stage_change_stop(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step(stop_on_stage_change=True)])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    stopped = automation_service.check_stage_change_stop(db_session, contact.id)
    assert len(stopped) == 1
    db_session.refresh(enrollment)
    assert enrollment.status == "stopped_stage_change"


def test_check_stage_change_stop_respects_flag(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step(stop_on_stage_change=False)])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    stopped = automation_service.check_stage_change_stop(db_session, contact.id)
    assert stopped == []
    db_session.refresh(enrollment)
    assert enrollment.status == "active"


def test_check_optout_stop_only_stops_sms_sequences(db_session, contact):
    sms_seq = _seq(db_session, name="SMS Seq", steps=[_basic_sms_step()])
    email_seq = _seq(db_session, name="Email Seq", steps=[_basic_email_step()])

    sms_enrollment = automation_service.enroll_contact(
        db_session, contact.id, sms_seq.id
    ).enrollment
    email_enrollment = automation_service.enroll_contact(
        db_session, contact.id, email_seq.id
    ).enrollment

    stopped = automation_service.check_optout_stop(db_session, contact.id)
    assert len(stopped) == 1
    assert stopped[0].id == sms_enrollment.id

    db_session.refresh(sms_enrollment)
    db_session.refresh(email_enrollment)
    assert sms_enrollment.status == "stopped_optout"
    assert email_enrollment.status == "active"


def test_check_reply_stop_ignores_completed_enrollments(db_session, contact):
    seq = _seq(db_session, steps=[_basic_sms_step()])
    enrollment = automation_service.enroll_contact(
        db_session, contact.id, seq.id
    ).enrollment
    enrollment.status = "completed"
    enrollment.completed_at = datetime.now(tz=timezone.utc)
    db_session.commit()
    stopped = automation_service.check_reply_stop(db_session, contact.id)
    assert stopped == []


# ---------------------------------------------------------------------------
# Log records
# ---------------------------------------------------------------------------
def test_automation_log_persisted_for_every_step(
    db_session, contact, sms_env, mock_twilio
):
    seq = _seq(
        db_session,
        steps=[
            _basic_sms_step(order=1, body="one"),
            _basic_sms_step(order=2, body="two"),
        ],
    )
    enrollment = _enroll_due_now(db_session, contact.id, seq.id)
    automation_service.process_pending_steps(db_session)
    enrollment.next_step_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    automation_service.process_pending_steps(db_session)
    logs = (
        db_session.query(AutomationLog)
        .filter(AutomationLog.enrollment_id == enrollment.id)
        .order_by(AutomationLog.id)
        .all()
    )
    assert len(logs) == 2
    assert [l.rendered_body for l in logs] == ["one", "two"]
    assert all(l.status == "sent" for l in logs)
