"""Sprint 19d — automation briefing summary + renderer card tests."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.automation import (
    AutomationEnrollment,
    AutomationLog,
    AutomationSequence,
    AutomationStep,
)
from app.models.contact import Contact
from app.services import briefing_filters, briefing_renderer


@pytest.fixture()
def fixed_now(monkeypatch):
    now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(briefing_filters, "_now_utc", lambda: now)
    return now


@pytest.fixture()
def seed_sequence(db_session):
    seq = AutomationSequence(
        name="Test Seq",
        trigger_type="contact_created",
        trigger_config={},
        is_active=True,
    )
    db_session.add(seq)
    db_session.flush()
    step = AutomationStep(
        sequence_id=seq.id,
        step_order=1,
        channel="sms",
        delay_minutes=0,
        template_body="Hi {first_name}",
    )
    db_session.add(step)
    contact = Contact(name="Alice", phone="(765) 555-0181")
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(seq)
    db_session.refresh(step)
    db_session.refresh(contact)
    return seq, step, contact


def _yesterday_dt(fixed_now):
    return fixed_now - timedelta(days=1)


def _today_start(fixed_now):
    return fixed_now.replace(hour=0, minute=0, second=0, microsecond=0)


def test_summary_returns_zeroes_on_empty_db(db_session, fixed_now):
    summary = briefing_filters.get_automation_briefing_summary(
        db_session, now=fixed_now
    )
    assert summary == {
        "active_enrollments": 0,
        "messages_sent_yesterday": 0,
        "messages_pending_today": 0,
        "reply_stops_yesterday": 0,
        "completed_yesterday": [],
        "paused_sequences": [],
    }


def test_summary_counts_match_seeded_state(
    db_session, fixed_now, seed_sequence
):
    seq, step, contact = seed_sequence
    today_start = _today_start(fixed_now)
    yesterday = _yesterday_dt(fixed_now)

    # Active enrollment with next step today.
    active = AutomationEnrollment(
        sequence_id=seq.id,
        contact_id=contact.id,
        current_step_order=1,
        status="active",
        next_step_at=today_start + timedelta(hours=3),
    )
    db_session.add(active)
    db_session.flush()

    # Sent log yesterday.
    db_session.add(
        AutomationLog(
            enrollment_id=active.id,
            step_id=step.id,
            channel="sms",
            rendered_body="x",
            status="sent",
            created_at=yesterday,
        )
    )
    db_session.commit()

    # Reply-stop enrollment from yesterday.
    bob = Contact(name="Bob", phone="(765) 555-0166")
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)
    reply_enrollment = AutomationEnrollment(
        sequence_id=seq.id,
        contact_id=bob.id,
        current_step_order=1,
        status="stopped_reply",
        stopped_at=yesterday,
    )
    db_session.add(reply_enrollment)
    db_session.commit()

    summary = briefing_filters.get_automation_briefing_summary(
        db_session, now=fixed_now
    )
    assert summary["active_enrollments"] == 1
    assert summary["messages_sent_yesterday"] == 1
    assert summary["messages_pending_today"] == 1
    assert summary["reply_stops_yesterday"] == 1


def test_summary_ignores_old_logs(db_session, fixed_now, seed_sequence):
    seq, step, contact = seed_sequence
    # A log from two days ago should not count.
    two_days_ago = fixed_now - timedelta(days=2, hours=1)
    enrollment = AutomationEnrollment(
        sequence_id=seq.id,
        contact_id=contact.id,
        current_step_order=1,
        status="active",
    )
    db_session.add(enrollment)
    db_session.flush()
    db_session.add(
        AutomationLog(
            enrollment_id=enrollment.id,
            step_id=step.id,
            channel="sms",
            rendered_body="x",
            status="sent",
            created_at=two_days_ago,
        )
    )
    db_session.commit()
    summary = briefing_filters.get_automation_briefing_summary(
        db_session, now=fixed_now
    )
    assert summary["messages_sent_yesterday"] == 0


def test_summary_completed_yesterday_lists_contacts(
    db_session, fixed_now, seed_sequence
):
    seq, step, contact = seed_sequence
    completed = AutomationEnrollment(
        sequence_id=seq.id,
        contact_id=contact.id,
        current_step_order=1,
        status="completed",
        completed_at=_yesterday_dt(fixed_now),
    )
    db_session.add(completed)
    db_session.commit()
    summary = briefing_filters.get_automation_briefing_summary(
        db_session, now=fixed_now
    )
    assert len(summary["completed_yesterday"]) == 1
    item = summary["completed_yesterday"][0]
    assert item["contact_name"] == "Alice"
    assert item["sequence_name"] == "Test Seq"


def test_summary_paused_sequences(db_session, fixed_now, seed_sequence):
    seq, _step, _contact = seed_sequence
    seq.is_active = False
    db_session.commit()
    summary = briefing_filters.get_automation_briefing_summary(
        db_session, now=fixed_now
    )
    assert summary["paused_sequences"] == ["Test Seq"]


# ---------------------------------------------------------------------------
# Renderer card
# ---------------------------------------------------------------------------
def test_card_omitted_when_all_zero():
    out = briefing_renderer._automations_card(
        {
            "active_enrollments": 0,
            "messages_sent_yesterday": 0,
            "messages_pending_today": 0,
            "reply_stops_yesterday": 0,
            "completed_yesterday": [],
            "paused_sequences": [],
        }
    )
    assert out == ""


def test_card_renders_with_counts():
    out = briefing_renderer._automations_card(
        {
            "active_enrollments": 12,
            "messages_sent_yesterday": 4,
            "messages_pending_today": 3,
            "reply_stops_yesterday": 2,
            "completed_yesterday": [],
            "paused_sequences": [],
        }
    )
    assert "AUTOMATIONS" in out.upper()
    assert ">12<" in out  # active count
    assert ">4<" in out and "messages sent yesterday" in out
    assert ">3<" in out and "messages scheduled today" in out
    assert "contacts replied" in out


def test_card_shows_paused_list_when_present():
    out = briefing_renderer._automations_card(
        {
            "active_enrollments": 0,
            "messages_sent_yesterday": 0,
            "messages_pending_today": 0,
            "reply_stops_yesterday": 0,
            "completed_yesterday": [],
            "paused_sequences": ["Cold Re-Engagement"],
        }
    )
    # Card should render because paused sequences are themselves notable.
    assert "paused" in out.lower()
    assert "Cold Re-Engagement" in out


# ---------------------------------------------------------------------------
# View injection
# ---------------------------------------------------------------------------
def test_dale_view_exposes_automations():
    view = briefing_filters.dale_view(
        {"automation_summary": {"active_enrollments": 7}},
        briefing_date="2026-05-19",
        yesterday="2026-05-18",
    )
    assert view["automations"]["active_enrollments"] == 7


def test_marcus_view_exposes_automations():
    view = briefing_filters.marcus_view(
        {"automation_summary": {"messages_sent_yesterday": 2}},
        briefing_date="2026-05-19",
        yesterday="2026-05-18",
    )
    assert view["automations"]["messages_sent_yesterday"] == 2
