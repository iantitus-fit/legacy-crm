"""Tests for the briefing sender orchestrator."""

from unittest.mock import MagicMock, patch

from app.services import briefing_sender


def _stub_briefing_data():
    return {
        "overdue_followups": [],
        "unsigned_estimates": {"viewed_not_signed": [], "not_viewed": [], "aging_over_5_days": []},
        "overdue_invoices": [],
        "unpaid_invoices": [],
        "upcoming_appointments": [],
        "tasks_due": [],
        "recent_customer_actions": [],
        "overnight_ai_actions": [],
        "stale_leads": [],
        "summary_counts": {},
    }


def test_send_morning_briefing_dry_run_returns_html(monkeypatch):
    monkeypatch.setenv("BRIEFING_EMAIL_DALE", "dale@test.com")
    monkeypatch.setenv("BRIEFING_EMAIL_MARCUS", "marcus@test.com")
    monkeypatch.setattr(briefing_sender, "get_briefing_context",
                        lambda *, db, user_id: _stub_briefing_data())
    fake_send = MagicMock()
    monkeypatch.setattr(briefing_sender, "send_email", fake_send)

    # Stub user resolution so we don't need a real DB
    monkeypatch.setattr(briefing_sender, "_resolve_user_id", lambda db: 1)

    result = briefing_sender.send_morning_briefing(
        db=MagicMock(), recipient="dale", dry_run=True,
    )
    assert "sent_to" in result
    assert result["sent_to"] == []  # dry run, nothing sent
    assert "previews" in result
    assert len(result["previews"]) == 1
    p = result["previews"][0]
    assert p["recipient"] == "dale"
    assert "<html>" in p["html"]
    assert p["subject"].startswith("Legacy briefing")
    assert fake_send.call_count == 0


def test_send_morning_briefing_real_send_calls_smtp(monkeypatch):
    monkeypatch.setenv("BRIEFING_EMAIL_DALE", "dale@test.com")
    monkeypatch.setenv("BRIEFING_EMAIL_MARCUS", "marcus@test.com")
    monkeypatch.setattr(briefing_sender, "get_briefing_context",
                        lambda *, db, user_id: _stub_briefing_data())
    monkeypatch.setattr(briefing_sender, "_resolve_user_id", lambda db: 1)
    fake_send = MagicMock(return_value=True)
    monkeypatch.setattr(briefing_sender, "send_email", fake_send)

    result = briefing_sender.send_morning_briefing(
        db=MagicMock(), recipient="all", dry_run=False,
    )
    assert sorted(result["sent_to"]) == ["dale@test.com", "marcus@test.com"]
    assert fake_send.call_count == 2


def test_send_morning_briefing_missing_env_var_skips_recipient(monkeypatch, caplog):
    monkeypatch.delenv("BRIEFING_EMAIL_DALE", raising=False)
    monkeypatch.setenv("BRIEFING_EMAIL_MARCUS", "marcus@test.com")
    monkeypatch.setattr(briefing_sender, "get_briefing_context",
                        lambda *, db, user_id: _stub_briefing_data())
    monkeypatch.setattr(briefing_sender, "_resolve_user_id", lambda db: 1)
    fake_send = MagicMock()
    monkeypatch.setattr(briefing_sender, "send_email", fake_send)

    result = briefing_sender.send_morning_briefing(
        db=MagicMock(), recipient="all", dry_run=False,
    )
    assert result["sent_to"] == ["marcus@test.com"]
    assert "dale" in str(result["skipped"]).lower()
    assert fake_send.call_count == 1


def test_send_morning_briefing_recipient_marcus_sends_marcus_only(monkeypatch):
    monkeypatch.setenv("BRIEFING_EMAIL_DALE", "dale@test.com")
    monkeypatch.setenv("BRIEFING_EMAIL_MARCUS", "marcus@test.com")
    monkeypatch.setattr(briefing_sender, "get_briefing_context",
                        lambda *, db, user_id: _stub_briefing_data())
    monkeypatch.setattr(briefing_sender, "_resolve_user_id", lambda db: 1)
    fake_send = MagicMock()
    monkeypatch.setattr(briefing_sender, "send_email", fake_send)

    result = briefing_sender.send_morning_briefing(
        db=MagicMock(), recipient="marcus", dry_run=False,
    )
    assert result["sent_to"] == ["marcus@test.com"]
    assert fake_send.call_count == 1
    args, _ = fake_send.call_args
    assert args[0] == "marcus@test.com"
