"""Adapt get_briefing_context() output into the recipient-specific view
dicts that briefing_renderer expects.

Two public entrypoints: dale_view(briefing_data) and marcus_view(briefing_data).
Helpers (prefixed with _) translate field names and shapes between the
briefing endpoint's structure and what the email renderer needs.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.automation import (
    AutomationEnrollment,
    AutomationLog,
    AutomationSequence,
)


def _now_utc() -> datetime:
    """Indirection for testability — monkeypatch in tests to freeze time."""
    return datetime.now(timezone.utc)


def _to_float(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(Decimal(str(v)))
    except (InvalidOperation, ValueError):
        return 0.0


def _adapt_invoice(inv: Dict[str, Any]) -> Dict[str, Any]:
    """Briefing invoice row -> renderer invoice row.

    Renames: balance -> amount, invoice_number -> id + memo.
    Fills contact_name with em-dash when missing.
    """
    return {
        "id": inv.get("invoice_number") or f"INV-{inv.get('id', '?')}",
        "contact_name": inv.get("contact_name") or "—",
        "contact_id": inv.get("contact_id"),
        "amount": _to_float(inv.get("balance")),
        "days_overdue": inv.get("days_overdue", 0),
        "memo": inv.get("invoice_number") or "",
        "due_date": inv.get("due_date") or "",
        "status": inv.get("status"),
    }


def _adapt_estimate(est: Dict[str, Any]) -> Dict[str, Any]:
    """Briefing estimate row -> renderer estimate row.

    Adds: amount (from total), scope (from name), age_days (computed).
    """
    created_iso = est.get("created_at")
    age_days = 0
    if created_iso:
        try:
            created = datetime.fromisoformat(created_iso)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = (_now_utc() - created).days
        except (ValueError, TypeError):
            age_days = 0
    return {
        "id": est.get("id"),
        "contact_name": est.get("contact_name") or "—",
        "contact_id": est.get("contact_id"),
        "scope": est.get("name") or "",
        "amount": _to_float(est.get("total")),
        "status": est.get("status"),
        "age_days": age_days,
    }


def _adapt_stale_lead(lead: Dict[str, Any], today_iso: str) -> Dict[str, Any]:
    """Briefing stale_lead row -> renderer cold_lead row."""
    today = date.fromisoformat(today_iso)
    days_since = 0
    last = lead.get("last_activity")
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            days_since = (today - last_dt.date()).days
        except (ValueError, TypeError):
            days_since = 0
    return {
        "name": lead.get("contact_name") or "—",
        "phone": lead.get("contact_phone") or "",
        "source": lead.get("lead_source") or "—",
        "lead_note": "",
        "days_since_touch": days_since,
        "contact_id": lead.get("contact_id"),
    }


def _adapt_ai_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """Briefing AI-action row -> renderer ai_recap item.

    Synthesizes a summary from the event_type and linked entity ids.
    """
    event_type = action.get("event_type") or "unknown"
    contact_id = action.get("contact_id")
    estimate_id = action.get("estimate_id")
    label = event_type.replace("_", " ").title()
    bits = [label]
    if estimate_id:
        bits.append(f"estimate #{estimate_id}")
    elif contact_id:
        bits.append(f"contact #{contact_id}")
    summary = " · ".join(bits)
    return {
        "action_type": event_type,
        "summary": summary,
        "created_at": action.get("created_at"),
    }


def _adapt_customer_action(a: Dict[str, Any]) -> Dict[str, Any]:
    """Briefing customer_action row -> renderer yesterday_signal item.

    Renames estimate_approved -> estimate_signed (renderer's green-pill key).
    Surfaces payment amounts.
    """
    src = a.get("type") or ""
    if src == "estimate_approved":
        kind = "estimate_signed"
        summary = f"Estimate #{a.get('estimate_id')} signed"
        amount = None
    elif src == "estimate_viewed":
        kind = "estimate_viewed"
        summary = f"Estimate #{a.get('estimate_id')} viewed"
        amount = None
    elif src == "payment":
        kind = "payment_received"
        summary = f"Payment on invoice #{a.get('invoice_id')}"
        amount = _to_float(a.get("amount"))
    else:
        kind = src
        summary = src.replace("_", " ").title()
        amount = None
    return {
        "type": kind,
        "summary": summary,
        "amount": amount,
        "at": a.get("at"),
    }


def dale_view(
    briefing_data: Dict[str, Any],
    *,
    briefing_date: str,
    yesterday: str,
) -> Dict[str, Any]:
    """Build the Dale (Owner — Sales & Cash) view dict for the email renderer."""
    unsigned = briefing_data.get("unsigned_estimates", {}) or {}
    pipeline = {
        "warm": [_adapt_estimate(e) for e in unsigned.get("viewed_not_signed", [])],
        "sent_not_viewed": [_adapt_estimate(e) for e in unsigned.get("not_viewed", [])],
        "aging": [_adapt_estimate(e) for e in unsigned.get("aging_over_5_days", [])],
    }
    cash_watch = {
        "overdue": [_adapt_invoice(i) for i in briefing_data.get("overdue_invoices", [])],
        "unpaid": [_adapt_invoice(i) for i in briefing_data.get("unpaid_invoices", [])],
    }
    cold_leads = [
        _adapt_stale_lead(l, today_iso=briefing_date)
        for l in briefing_data.get("stale_leads", [])
    ][:5]
    yesterday_signals = [
        _adapt_customer_action(a)
        for a in briefing_data.get("recent_customer_actions", [])
    ]
    ai_items = [
        _adapt_ai_action(a)
        for a in briefing_data.get("overnight_ai_actions", [])
    ]
    return {
        "recipient": "Dale",
        "role": "Owner • Sales & Cash",
        "weather": None,
        "ai_recap": {"total": len(ai_items), "items": ai_items},
        "yesterday_signals": yesterday_signals,
        "new_leads": [],
        "estimate_pipeline": pipeline,
        "lead_sources": briefing_data.get("lead_source_summary") or {},
        "automations": briefing_data.get("automation_summary") or {},
        "cash_watch": cash_watch,
        "cold_leads": cold_leads,
        "briefing_date": briefing_date,
        "yesterday": yesterday,
    }


def marcus_view(
    briefing_data: Dict[str, Any],
    *,
    briefing_date: str,
    yesterday: str,
) -> Dict[str, Any]:
    """Build the Marcus (Operations Manager — Crews & Jobs) view dict."""
    # Jobs today: filter upcoming_appointments to today's date
    jobs_today: List[Dict[str, Any]] = []
    for appt in briefing_data.get("upcoming_appointments", []):
        if appt.get("date") == briefing_date:
            jobs_today.append({
                "id": appt.get("id"),
                "title": appt.get("title", ""),
                "address": "",
                "start_time": (appt.get("time") or "")[:5],
                "needs_crew": False,
                "crew_name": None,
                "crew_lead": None,
                "contact_name": appt.get("contact_name") or "—",
            })
    # Tasks: split tasks_due into overdue + due_today
    tasks_overdue: List[Dict[str, Any]] = []
    tasks_due_today: List[Dict[str, Any]] = []
    for t in briefing_data.get("tasks_due", []):
        days_overdue = t.get("days_overdue") or 0
        row = {
            "id": t.get("id"),
            "title": t.get("title", ""),
            "days_overdue": days_overdue,
            "contact_name": "",
        }
        if days_overdue > 0:
            tasks_overdue.append(row)
        else:
            tasks_due_today.append(row)
    # signed_yesterday: filter recent_customer_actions for estimate_approved
    signed_yesterday: List[Dict[str, Any]] = []
    for a in briefing_data.get("recent_customer_actions", []):
        if a.get("type") == "estimate_approved":
            signed_yesterday.append({
                "id": a.get("estimate_id"),
                "contact_name": "—",
                "scope": "",
                "address": "",
                "amount": 0.0,
            })
    ai_items = [
        _adapt_ai_action(a)
        for a in briefing_data.get("overnight_ai_actions", [])
    ]
    return {
        "recipient": "Marcus",
        "role": "Operations Manager • Crews & Jobs",
        "weather": None,
        "ai_recap": {"total": len(ai_items), "items": ai_items},
        "jobs_today": jobs_today,
        "jobs_no_crew": [],
        "tasks": {"overdue": tasks_overdue, "due_today": tasks_due_today},
        "new_leads": [],
        "signed_yesterday": signed_yesterday,
        "automations": briefing_data.get("automation_summary") or {},
        "briefing_date": briefing_date,
        "yesterday": yesterday,
    }


# ---------------------------------------------------------------------------
# Sprint 19d — automation engine summary for the morning briefing
# ---------------------------------------------------------------------------
def get_automation_briefing_summary(
    db: Session, *, now: Optional[datetime] = None
) -> Dict[str, Any]:
    """Return automation activity counts for the morning briefing.

    Day boundaries are UTC. ``yesterday`` covers the previous calendar day
    (midnight-to-midnight UTC) and ``today`` covers today's calendar day so
    far. The "messages pending today" count is the number of active
    enrollments whose next scheduled step lands sometime today — a
    forward-looking signal for how many texts the engine plans to send.
    """
    if now is None:
        now = _now_utc()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    yesterday_start = today_start - timedelta(days=1)

    active_enrollments = (
        db.query(AutomationEnrollment)
        .filter(AutomationEnrollment.status == "active")
        .count()
    )
    messages_sent_yesterday = (
        db.query(AutomationLog)
        .filter(
            AutomationLog.status == "sent",
            AutomationLog.created_at >= yesterday_start,
            AutomationLog.created_at < today_start,
        )
        .count()
    )
    messages_pending_today = (
        db.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.status == "active",
            AutomationEnrollment.next_step_at.isnot(None),
            AutomationEnrollment.next_step_at >= today_start,
            AutomationEnrollment.next_step_at < today_end,
        )
        .count()
    )
    reply_stops_yesterday = (
        db.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.status == "stopped_reply",
            AutomationEnrollment.stopped_at >= yesterday_start,
            AutomationEnrollment.stopped_at < today_start,
        )
        .count()
    )

    completed_rows = (
        db.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.status == "completed",
            AutomationEnrollment.completed_at >= yesterday_start,
            AutomationEnrollment.completed_at < today_start,
        )
        .all()
    )
    completed_yesterday = [
        {
            "contact_name": (
                row.contact.name if row.contact else None
            ),
            "sequence_name": (
                row.sequence.name if row.sequence else None
            ),
        }
        for row in completed_rows
    ]

    paused_rows = (
        db.query(AutomationSequence)
        .filter(AutomationSequence.is_active.is_(False))
        .all()
    )
    paused_sequences = [s.name for s in paused_rows]

    return {
        "active_enrollments": active_enrollments,
        "messages_sent_yesterday": messages_sent_yesterday,
        "messages_pending_today": messages_pending_today,
        "reply_stops_yesterday": reply_stops_yesterday,
        "completed_yesterday": completed_yesterday,
        "paused_sequences": paused_sequences,
    }
