"""Smoke tests for the daily briefing HTML renderer."""

import os
from app.services import briefing_renderer


def _minimal_dale_view():
    return {
        "recipient": "Dale",
        "role": "Owner • Sales & Cash",
        "weather": None,
        "ai_recap": {"total": 0, "items": []},
        "yesterday_signals": [],
        "new_leads": [],
        "estimate_pipeline": {"warm": [], "sent_not_viewed": [], "aging": []},
        "cash_watch": {"overdue": [], "unpaid": []},
        "cold_leads": [],
        "briefing_date": "2026-05-15",
        "yesterday": "2026-05-14",
    }


def _minimal_marcus_view():
    return {
        "recipient": "Marcus",
        "role": "Operations Manager • Crews & Jobs",
        "weather": None,
        "ai_recap": {"total": 0, "items": []},
        "jobs_today": [],
        "jobs_no_crew": [],
        "tasks": {"due_today": [], "overdue": []},
        "new_leads": [],
        "signed_yesterday": [],
        "briefing_date": "2026-05-15",
        "yesterday": "2026-05-14",
    }


def test_render_dale_email_with_empty_view_does_not_crash():
    html = briefing_renderer.render_dale_email(_minimal_dale_view())
    assert "<html>" in html
    assert "Daily Briefing" in html
    assert "Morning Dale" in html
    # No weather card should render when weather is None
    assert "Kokomo · today" not in html


def test_render_marcus_email_with_empty_view_does_not_crash():
    html = briefing_renderer.render_marcus_email(_minimal_marcus_view())
    assert "<html>" in html
    assert "Morning Marcus" in html
    assert "Operations Manager" in html


def test_render_subject_dale_with_no_overdue_returns_simple_subject():
    subject = briefing_renderer.render_subject(_minimal_dale_view())
    assert subject.startswith("Legacy briefing · ")


def test_render_subject_marcus_with_signed_yesterday():
    view = _minimal_marcus_view()
    view["signed_yesterday"] = [{"id": 1, "contact_name": "X", "scope": "Y", "amount": 1000}]
    subject = briefing_renderer.render_subject(view)
    assert "1 signed → schedule" in subject


def test_render_subject_does_not_crash_when_weather_is_none():
    view = _minimal_dale_view()
    # weather=None must not blow up render_subject
    briefing_renderer.render_subject(view)


def test_open_in_crm_link_uses_portal_base_url(monkeypatch):
    monkeypatch.setenv("PORTAL_BASE_URL", "https://example.test")
    html = briefing_renderer.render_dale_email(_minimal_dale_view())
    assert 'href="https://example.test"' in html


def test_render_dale_with_data_includes_amounts(monkeypatch):
    view = _minimal_dale_view()
    view["cash_watch"]["overdue"] = [
        {
            "id": "INV-1",
            "contact_name": "Nora Whitfield",
            "amount": 8615.40,
            "days_overdue": 12,
            "memo": "INV-1",
            "due_date": "2026-05-03",
        }
    ]
    html = briefing_renderer.render_dale_email(view)
    assert "Nora Whitfield" in html
    assert "$8,615" in html
    assert "12d overdue" in html
