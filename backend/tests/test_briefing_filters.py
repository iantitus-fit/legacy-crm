"""Tests for dale_view / marcus_view adapters and field-shape helpers."""

from app.services import briefing_filters


def test_adapt_invoice_maps_balance_to_amount():
    inv = {
        "id": 7, "invoice_number": "INV-7", "status": "sent",
        "due_date": "2026-05-03",
        "days_overdue": 12,
        "balance": "8615.40",
        "total": "8615.40",
        "job_id": 4,
        "contact_id": 99,
        "contact_name": "Nora Whitfield",
    }
    out = briefing_filters._adapt_invoice(inv)
    assert out["id"] == "INV-7"
    assert out["contact_name"] == "Nora Whitfield"
    assert out["amount"] == 8615.40
    assert out["days_overdue"] == 12
    assert out["memo"] == "INV-7"
    assert out["due_date"] == "2026-05-03"


def test_adapt_invoice_handles_missing_contact_name():
    inv = {
        "id": 1, "invoice_number": "INV-1", "balance": "100", "total": "100",
        "due_date": "2026-05-03", "days_overdue": 0, "contact_name": None, "contact_id": None,
        "status": "sent", "job_id": 1,
    }
    out = briefing_filters._adapt_invoice(inv)
    assert out["contact_name"] == "—"


def test_adapt_estimate_computes_age_days(monkeypatch):
    from datetime import datetime, timezone, timedelta
    fixed_now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    monkeypatch.setattr(briefing_filters, "_now_utc", lambda: fixed_now)

    six_days_ago = (fixed_now - timedelta(days=6)).isoformat()
    est = {
        "id": 42, "name": "Roof replacement", "status": "viewed",
        "total": "12500.00",
        "created_at": six_days_ago,
        "contact_name": "Nora Whitfield", "contact_id": 1,
    }
    out = briefing_filters._adapt_estimate(est)
    assert out["age_days"] == 6
    assert out["amount"] == 12500.00
    assert out["scope"] == "Roof replacement"
    assert out["status"] == "viewed"
    assert out["contact_name"] == "Nora Whitfield"


def test_adapt_estimate_handles_missing_created_at():
    est = {
        "id": 1, "name": "X", "status": "sent",
        "total": "100", "created_at": None,
        "contact_name": "A", "contact_id": 1,
    }
    out = briefing_filters._adapt_estimate(est)
    assert out["age_days"] == 0


def test_adapt_stale_lead_renames_fields():
    lead = {
        "contact_id": 5, "contact_name": "Bob",
        "contact_phone": "(555) 123-4567",
        "lead_source": "Google LSA",
        "estimate_value": "5000",
        "last_activity": "2026-04-01T12:00:00+00:00",
    }
    out = briefing_filters._adapt_stale_lead(lead, today_iso="2026-05-15")
    assert out["name"] == "Bob"
    assert out["phone"] == "(555) 123-4567"
    assert out["source"] == "Google LSA"
    assert out["lead_note"] == ""
    assert out["days_since_touch"] == 44


def test_adapt_ai_action_renames_event_to_action_type():
    action = {
        "id": 1, "event_type": "estimate_sent",
        "status": "complete",
        "contact_id": 2, "estimate_id": 7,
        "created_at": "2026-05-15T06:30:00+00:00",
    }
    out = briefing_filters._adapt_ai_action(action)
    assert out["action_type"] == "estimate_sent"
    assert "Estimate Sent" in out["summary"] or "estimate" in out["summary"].lower()
    assert out["created_at"] == "2026-05-15T06:30:00+00:00"


def test_adapt_customer_action_renames_approved_to_signed():
    a = {
        "type": "estimate_approved",
        "estimate_id": 7,
        "at": "2026-05-14T15:00:00+00:00",
        "actor": "Customer",
    }
    out = briefing_filters._adapt_customer_action(a)
    assert out["type"] == "estimate_signed"
    assert "estimate" in out["summary"].lower()


def test_adapt_customer_action_payment_carries_amount():
    a = {
        "type": "payment",
        "invoice_id": 3,
        "amount": "500.00",
        "method": "check",
        "at": "2026-05-14T10:00:00+00:00",
    }
    out = briefing_filters._adapt_customer_action(a)
    assert out["type"] == "payment_received"
    assert out["amount"] == 500.0


def _sample_briefing_data():
    return {
        "overdue_followups": [],
        "unsigned_estimates": {
            "viewed_not_signed": [
                {"id": 1, "name": "Estimate #1", "status": "viewed",
                 "total": "5000", "created_at": "2026-05-13T00:00:00+00:00",
                 "contact_name": "A", "contact_id": 1},
            ],
            "not_viewed": [
                {"id": 2, "name": "Estimate #2", "status": "sent",
                 "total": "3000", "created_at": "2026-05-14T00:00:00+00:00",
                 "contact_name": "B", "contact_id": 2},
            ],
            "aging_over_5_days": [
                {"id": 3, "name": "Estimate #3", "status": "viewed",
                 "total": "9000", "created_at": "2026-05-01T00:00:00+00:00",
                 "contact_name": "C", "contact_id": 3},
            ],
        },
        "overdue_invoices": [
            {"id": 7, "invoice_number": "INV-7", "status": "sent",
             "due_date": "2026-05-03", "days_overdue": 12,
             "balance": "8615.40", "total": "8615.40", "job_id": 4,
             "contact_id": 1, "contact_name": "Nora Whitfield"},
        ],
        "unpaid_invoices": [
            {"id": 8, "invoice_number": "INV-8", "status": "sent",
             "due_date": "2026-05-20", "balance": "500", "total": "500",
             "job_id": 5, "contact_id": 2, "contact_name": "Bob"},
        ],
        "upcoming_appointments": [
            {"id": 100, "title": "Inspection", "date": "2026-05-15",
             "time": "09:00:00", "duration_minutes": 60, "type": "inspection",
             "contact_id": 1, "contact_name": "Nora Whitfield",
             "assigned_to_user_id": 1},
        ],
        "tasks_due": [
            {"id": 50, "title": "Call back Bob", "status": "open",
             "due_date": "2026-05-14", "days_overdue": 1,
             "assigned_to_user_id": 1, "related_entity_type": "contact",
             "related_entity_id": 2},
            {"id": 51, "title": "Order shingles", "status": "open",
             "due_date": "2026-05-15", "days_overdue": 0,
             "assigned_to_user_id": 1, "related_entity_type": None,
             "related_entity_id": None},
        ],
        "recent_customer_actions": [
            {"type": "estimate_approved", "estimate_id": 9,
             "at": "2026-05-14T15:00:00+00:00", "actor": "Customer"},
            {"type": "payment", "invoice_id": 3, "amount": "500.00",
             "method": "check", "at": "2026-05-14T10:00:00+00:00"},
        ],
        "overnight_ai_actions": [
            {"id": 1, "event_type": "estimate_sent", "status": "complete",
             "contact_id": 2, "estimate_id": 9,
             "created_at": "2026-05-15T06:30:00+00:00"},
        ],
        "stale_leads": [
            {"contact_id": 99, "contact_name": "Cold Carl",
             "contact_phone": "(555) 000-0000",
             "lead_source": "Yard Sign", "estimate_value": "0",
             "last_activity": "2026-04-01T00:00:00+00:00"},
        ],
        "summary_counts": {},
        "generated_at": "2026-05-15T07:00:00+00:00",
    }


def test_dale_view_shape():
    bd = _sample_briefing_data()
    v = briefing_filters.dale_view(bd, briefing_date="2026-05-15", yesterday="2026-05-14")
    assert v["recipient"] == "Dale"
    assert v["role"] == "Owner • Sales & Cash"
    assert v["weather"] is None
    assert v["ai_recap"]["total"] == 1
    assert v["ai_recap"]["items"][0]["action_type"] == "estimate_sent"
    assert len(v["yesterday_signals"]) == 2
    signed = [s for s in v["yesterday_signals"] if s["type"] == "estimate_signed"]
    assert len(signed) == 1
    assert v["new_leads"] == []
    assert len(v["estimate_pipeline"]["warm"]) == 1
    assert v["estimate_pipeline"]["warm"][0]["contact_name"] == "A"
    assert len(v["estimate_pipeline"]["sent_not_viewed"]) == 1
    assert len(v["estimate_pipeline"]["aging"]) == 1
    assert len(v["cash_watch"]["overdue"]) == 1
    assert v["cash_watch"]["overdue"][0]["amount"] == 8615.40
    assert len(v["cash_watch"]["unpaid"]) == 1
    assert len(v["cold_leads"]) == 1
    assert v["cold_leads"][0]["name"] == "Cold Carl"
    assert v["briefing_date"] == "2026-05-15"
    assert v["yesterday"] == "2026-05-14"


def test_dale_view_cold_leads_capped_at_5():
    bd = _sample_briefing_data()
    bd["stale_leads"] = [
        {"contact_id": i, "contact_name": f"Lead {i}",
         "contact_phone": "", "lead_source": "X",
         "estimate_value": "0",
         "last_activity": "2026-04-01T00:00:00+00:00"}
        for i in range(10)
    ]
    v = briefing_filters.dale_view(bd, briefing_date="2026-05-15", yesterday="2026-05-14")
    assert len(v["cold_leads"]) == 5


def test_marcus_view_shape():
    bd = _sample_briefing_data()
    v = briefing_filters.marcus_view(bd, briefing_date="2026-05-15", yesterday="2026-05-14")
    assert v["recipient"] == "Marcus"
    assert v["role"] == "Operations Manager • Crews & Jobs"
    assert v["weather"] is None
    assert v["ai_recap"]["total"] == 1
    # jobs_today filters upcoming_appointments to today's date (2026-05-15)
    assert len(v["jobs_today"]) == 1
    assert v["jobs_today"][0]["title"] == "Inspection"
    # jobs_no_crew is empty in v1
    assert v["jobs_no_crew"] == []
    # tasks split: 1 overdue, 1 due today
    assert len(v["tasks"]["overdue"]) == 1
    assert v["tasks"]["overdue"][0]["title"] == "Call back Bob"
    assert len(v["tasks"]["due_today"]) == 1
    assert v["tasks"]["due_today"][0]["title"] == "Order shingles"
    # signed_yesterday filters recent_customer_actions for estimate_approved
    assert len(v["signed_yesterday"]) == 1
    assert v["new_leads"] == []
