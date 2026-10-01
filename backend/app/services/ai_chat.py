"""Conversational AI service.

Exposes start_conversation/continue_conversation for the chat panel and
get_briefing_context for the morning briefing data endpoint.

All LLM calls go through ai_provider.get_provider(). When the provider is
NoneProvider, assistant messages are persisted with empty content so the
conversation history remains consistent — the panel renders an inline
"AI provider not configured" warning rather than blocking.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.ai_action import AIAction
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.estimate_status_history import EstimateStatusHistory
from app.models.invoice import Invoice
from app.models.note import Note
from app.models.payment import Payment
from app.models.pipeline import Pipeline
from app.models.task import Task
from app.services import ai_events
from app.services.ai_prompts import render_prompt
from app.services.ai_provider import AIProvider, get_provider

logger = logging.getLogger("legacy_crm.ai")

MAX_HISTORY_MESSAGES = 20
TITLE_MAX_LEN = 80


# ---------- Public API ----------


def start_conversation(
    *,
    db: Session,
    user_id: int,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    initial_message: str,
    provider: Optional[AIProvider] = None,
) -> Tuple[AIConversation, AIMessage]:
    """Create a new conversation, persist initial user message, generate
    assistant reply, persist assistant message, return both."""
    convo = AIConversation(
        id=uuid.uuid4().hex,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        title=_derive_title(initial_message),
    )
    db.add(convo)
    db.flush()

    user_msg = _persist_message(db, convo.id, "user", initial_message)
    assistant_msg = _generate_and_persist(
        db=db,
        convo=convo,
        user_message_text=initial_message,
        history=[user_msg],
        provider=provider,
    )

    convo.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(convo)
    db.refresh(assistant_msg)
    return convo, assistant_msg


def continue_conversation(
    *,
    db: Session,
    conversation_id: str,
    user_message: str,
    provider: Optional[AIProvider] = None,
) -> AIMessage:
    """Append a user message to an existing conversation and generate an
    assistant reply. Returns the assistant message."""
    convo = (
        db.query(AIConversation)
        .filter(AIConversation.id == conversation_id)
        .first()
    )
    if convo is None:
        raise ValueError(f"Conversation {conversation_id!r} not found")

    history = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == convo.id)
        .order_by(AIMessage.created_at.asc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )

    user_msg = _persist_message(db, convo.id, "user", user_message)
    history.append(user_msg)

    assistant_msg = _generate_and_persist(
        db=db,
        convo=convo,
        user_message_text=user_message,
        history=history,
        provider=provider,
    )
    convo.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


# ---------- Internal helpers ----------


def _derive_title(text: str) -> str:
    cleaned = " ".join((text or "").split())
    return cleaned[:TITLE_MAX_LEN] if cleaned else "New conversation"


def _persist_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> AIMessage:
    msg = AIMessage(
        id=uuid.uuid4().hex,
        conversation_id=conversation_id,
        role=role,
        content=content,
        message_metadata=metadata,
    )
    db.add(msg)
    db.flush()
    return msg


def _build_system_prompt(db: Session, convo: AIConversation) -> str:
    """Pick the right system prompt template + entity context."""
    company_ctx = {
        "company_name": settings.ai_company_name,
        "company_phone": settings.ai_company_phone,
    }
    if convo.entity_type and convo.entity_id:
        entity_label, entity_context = _build_entity_context(
            db, convo.entity_type, convo.entity_id
        )
        ctx = {
            **company_ctx,
            "entity_label": entity_label,
            "entity_context": entity_context,
        }
        system, _ = render_prompt("conversation_with_entity", ctx)
        return system
    # Sprint 18a — inject lead source metrics for global (no-entity) queries.
    company_ctx["lead_source_context"] = _build_lead_source_context(db)
    # Sprint 19d — inject automation engine status for global queries.
    company_ctx["automations_context"] = _build_automations_context(db)
    system, _ = render_prompt("conversation_system", company_ctx)
    return system


def _build_lead_source_context(db: Session) -> str:
    """Pre-assembled lead source metrics for the global system prompt.

    The LLM reads this verbatim; the format is a compact human-readable
    summary, not raw JSON, so cheaper models can answer questions like
    "what's my close rate on Google LSA leads?" without parsing.
    """
    from app.services.reports import get_lead_source_report

    try:
        report = get_lead_source_report(db, period="all")
    except Exception:
        return "(lead source metrics unavailable)"

    if not report["sources"] and report["unattributed"]["lead_count"] == 0:
        return "(no lead source data yet)"

    lines = [
        f"Total leads (all time): {report['total_leads']}",
        f"Total revenue collected: ${report['total_revenue']:,.2f}",
        "",
        "Per source:",
    ]
    for s in report["sources"]:
        avg_days = (
            f", avg {s['avg_days_to_close']}d to close"
            if s["avg_days_to_close"] is not None
            else ""
        )
        lines.append(
            f"- {s['source']}: {s['lead_count']} leads "
            f"({s['lead_percentage']}%), "
            f"{s['approved_count']} approved, "
            f"close rate {s['close_rate']}%, "
            f"avg job value ${s['avg_job_value']:,.0f}, "
            f"collected ${s['total_collected']:,.0f}"
            f"{avg_days}"
        )
    unatt = report["unattributed"]
    if unatt["lead_count"] > 0:
        lines.append(
            f"- Unattributed: {unatt['lead_count']} contacts with no "
            "lead_source value"
        )
    return "\n".join(lines)


def _build_automations_context(db: Session) -> str:
    """Pre-assembled automation engine snapshot for the global system prompt.

    Same format style as ``_build_lead_source_context`` — compact
    human-readable lines so cheaper LLMs can answer "how many contacts are
    in drip sequences?" or "which sequences are performing best?" without
    parsing JSON.
    """
    from sqlalchemy import func as sa_func

    from app.models.automation import (
        AutomationEnrollment,
        AutomationLog,
        AutomationSequence,
    )

    try:
        sequences = (
            db.query(AutomationSequence)
            .order_by(AutomationSequence.id)
            .all()
        )
    except Exception:
        return "(automation metrics unavailable)"

    if not sequences:
        return "(no automation sequences configured yet)"

    active_total = sum(1 for s in sequences if s.is_active)
    paused_total = len(sequences) - active_total

    active_enrollments = (
        db.query(sa_func.count(AutomationEnrollment.id))
        .filter(AutomationEnrollment.status == "active")
        .scalar()
        or 0
    )

    lines = [
        f"Total sequences: {len(sequences)} ({active_total} active, "
        f"{paused_total} paused)",
        f"Active enrollments right now: {active_enrollments}",
        "",
        "Per sequence:",
    ]

    for seq in sequences:
        enroll_counts = dict(
            db.query(
                AutomationEnrollment.status,
                sa_func.count(AutomationEnrollment.id),
            )
            .filter(AutomationEnrollment.sequence_id == seq.id)
            .group_by(AutomationEnrollment.status)
            .all()
        )
        total_enrolled = sum(enroll_counts.values())
        active = enroll_counts.get("active", 0)
        completed = enroll_counts.get("completed", 0)
        stopped_reply = enroll_counts.get("stopped_reply", 0)
        sent_count = (
            db.query(sa_func.count(AutomationLog.id))
            .join(
                AutomationEnrollment,
                AutomationLog.enrollment_id == AutomationEnrollment.id,
            )
            .filter(
                AutomationEnrollment.sequence_id == seq.id,
                AutomationLog.status == "sent",
            )
            .scalar()
            or 0
        )
        status_word = "active" if seq.is_active else "paused"
        reply_rate = (
            f", reply rate {stopped_reply / total_enrolled * 100:.0f}%"
            if total_enrolled
            else ""
        )
        lines.append(
            f"- {seq.name} [{status_word}, trigger={seq.trigger_type}]: "
            f"{total_enrolled} enrolled "
            f"({active} active, {completed} completed), "
            f"{sent_count} messages sent{reply_rate}"
        )
    return "\n".join(lines)


def _build_entity_context(
    db: Session, entity_type: str, entity_id: int
) -> Tuple[str, str]:
    """Return (label, context_text) for the system prompt."""
    if entity_type == "contact":
        contact = db.query(Contact).filter(Contact.id == entity_id).first()
        if contact is None:
            return ("Customer", "(customer not found)")
        lines = [
            f"Name: {contact.name}",
            f"Phone: {contact.phone or ''}",
            f"Email: {contact.email or ''}",
            f"Address: {contact.address or ''}",
            f"Lead Source: {contact.lead_source or ''}",
            f"Client Type: {contact.client_type or ''}",
            "",
            "Estimates:",
            ai_events._estimates_summary_for_contact(db, contact.id),
            "",
            "Recent Notes:",
            ai_events._all_notes_for_contact(db, contact.id),
            "",
            "Recent Activity:",
            ai_events._activity_summary_for_contact(db, contact.id),
        ]
        return ("Customer", "\n".join(lines))
    if entity_type == "estimate":
        estimate = db.query(Estimate).filter(Estimate.id == entity_id).first()
        if estimate is None:
            return ("Estimate", "(estimate not found)")
        contact_line = ""
        if estimate.job and estimate.job.contact:
            contact_line = (
                f"Customer: {estimate.job.contact.name}  |  "
                f"Phone: {estimate.job.contact.phone or ''}"
            )
        lines = [
            f"Estimate: {estimate.name or f'#{estimate.id}'}",
            f"Status: {estimate.status}",
            f"Total: ${estimate.total or 0}",
            contact_line,
            "",
            "Line Items:",
            ai_events._format_line_items(estimate),
        ]
        return ("Estimate", "\n".join(lines))
    return (entity_type.title(), "(unsupported entity type)")


def _build_user_prompt(history: List[AIMessage], current_user_text: str) -> str:
    """Format the full message history as a single user prompt with role markers.

    Recent messages only (last MAX_HISTORY_MESSAGES). The provider abstraction
    takes a single (system, user) pair, so history is serialized into the
    user prompt with role labels.
    """
    recent = history[-MAX_HISTORY_MESSAGES:]
    lines = []
    for m in recent:
        prefix = "User" if m.role == "user" else "Assistant"
        lines.append(f"{prefix}: {m.content}")
    if not recent or recent[-1].content != current_user_text:
        lines.append(f"User: {current_user_text}")
    lines.append("Assistant:")
    return "\n\n".join(lines)


def _generate_and_persist(
    *,
    db: Session,
    convo: AIConversation,
    user_message_text: str,
    history: List[AIMessage],
    provider: Optional[AIProvider],
) -> AIMessage:
    system_prompt = _build_system_prompt(db, convo)
    user_prompt = _build_user_prompt(history, user_message_text)
    active = provider or get_provider()
    response = active.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    metadata = {
        "provider": response.provider,
        "model": response.model,
        "tokens_used": response.tokens_used,
        "duration_ms": response.duration_ms,
        "success": response.success,
        "error": response.error,
    }
    return _persist_message(
        db,
        conversation_id=convo.id,
        role="assistant",
        content=response.content or "",
        metadata=metadata,
    )


# ---------- Morning briefing ----------

INDIANA_TZ = ZoneInfo("America/Indiana/Indianapolis")
STALE_LEAD_DAYS = 14
OVERDUE_FOLLOWUP_DAYS = 3
AGING_ESTIMATE_DAYS = 5
RECENT_ACTION_HOURS = 24


def get_briefing_context(*, db: Session, user_id: int) -> Dict[str, Any]:
    """Assemble the morning briefing data dict.

    No LLM is involved. This is the structured-data endpoint that powers
    both the in-CRM panel (via /api/ai/briefing/narrative) and external
    consumers like HyperAgent (via /api/ai/briefing).
    """
    now_local = datetime.now(INDIANA_TZ)
    today = now_local.date()
    overdue_invoices = _briefing_overdue_invoices(db, today)
    unpaid_invoices = _briefing_unpaid_invoices(db, today)
    tasks_due = _briefing_tasks_due(db, today, user_id)
    upcoming_appointments = _briefing_upcoming_appointments(db, today, user_id)
    overdue_followups = _briefing_overdue_followups(db, today)
    unsigned = _briefing_unsigned_estimates(db, now_local)
    stale_leads = _briefing_stale_leads(db, today)
    recent_actions = _briefing_recent_customer_actions(db, now_local)
    overnight_ai = _briefing_overnight_ai_actions(db, now_local)
    from app.services.briefing_filters import get_automation_briefing_summary
    from app.services.reports import get_lead_source_briefing_summary

    lead_source_summary = get_lead_source_briefing_summary(db, now=today)
    automation_summary = get_automation_briefing_summary(db)

    summary_counts = {
        "overdue_followups": len(overdue_followups),
        "unsigned_estimates": (
            len(unsigned["viewed_not_signed"])
            + len(unsigned["not_viewed"])
            + len(unsigned["aging_over_5_days"])
        ),
        "overdue_invoices": len(overdue_invoices),
        "unpaid_invoices": len(unpaid_invoices),
        "upcoming_appointments": len(upcoming_appointments),
        "tasks_due": len(tasks_due),
        "recent_customer_actions": len(recent_actions),
        "overnight_ai_actions": len(overnight_ai),
        "stale_leads": len(stale_leads),
    }

    return {
        "overdue_followups": overdue_followups,
        "unsigned_estimates": unsigned,
        "overdue_invoices": overdue_invoices,
        "unpaid_invoices": unpaid_invoices,
        "upcoming_appointments": upcoming_appointments,
        "tasks_due": tasks_due,
        "recent_customer_actions": recent_actions,
        "overnight_ai_actions": overnight_ai,
        "stale_leads": stale_leads,
        "lead_source_summary": lead_source_summary,
        "automation_summary": automation_summary,
        "summary_counts": summary_counts,
        "generated_at": datetime.now(timezone.utc),
    }


def _briefing_overdue_invoices(db: Session, today: date) -> List[Dict[str, Any]]:
    from app.models.job import Job

    rows = (
        db.query(Invoice, Contact)
        .join(Job, Job.id == Invoice.job_id)
        .outerjoin(Contact, Contact.id == Job.contact_id)
        .filter(Invoice.due_date < today)
        .filter(Invoice.balance > 0)
        .filter(Invoice.status != "void")
        .order_by(Invoice.due_date.asc())
        .all()
    )
    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "status": inv.status,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "days_overdue": (today - inv.due_date).days if inv.due_date else 0,
            "balance": str(inv.balance),
            "total": str(inv.total),
            "job_id": inv.job_id,
            "contact_id": contact.id if contact else None,
            "contact_name": contact.name if contact else None,
        }
        for inv, contact in rows
    ]


def _briefing_unpaid_invoices(db: Session, today: date) -> List[Dict[str, Any]]:
    from app.models.job import Job

    rows = (
        db.query(Invoice, Contact)
        .join(Job, Job.id == Invoice.job_id)
        .outerjoin(Contact, Contact.id == Job.contact_id)
        .filter(Invoice.balance > 0)
        .filter(Invoice.status != "void")
        .filter(or_(Invoice.due_date >= today, Invoice.due_date.is_(None)))
        .order_by(Invoice.due_date.asc().nullslast())
        .all()
    )
    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "status": inv.status,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "balance": str(inv.balance),
            "total": str(inv.total),
            "job_id": inv.job_id,
            "contact_id": contact.id if contact else None,
            "contact_name": contact.name if contact else None,
        }
        for inv, contact in rows
    ]


def _briefing_tasks_due(
    db: Session, today: date, user_id: int
) -> List[Dict[str, Any]]:
    rows = (
        db.query(Task)
        .filter(Task.status != "done")
        .filter(Task.due_date <= today)
        .order_by(Task.due_date.asc())
        .all()
    )
    return [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "days_overdue": (today - t.due_date).days if t.due_date else 0,
            "assigned_to_user_id": t.assigned_to_user_id,
            "related_entity_type": t.related_entity_type,
            "related_entity_id": t.related_entity_id,
        }
        for t in rows
    ]


def _briefing_upcoming_appointments(
    db: Session, today: date, user_id: int
) -> List[Dict[str, Any]]:
    cutoff = today + timedelta(days=7)
    rows = (
        db.query(Appointment, Contact)
        .outerjoin(Contact, Contact.id == Appointment.contact_id)
        .filter(Appointment.appointment_date >= today)
        .filter(Appointment.appointment_date <= cutoff)
        .order_by(Appointment.appointment_date.asc())
        .all()
    )
    return [
        {
            "id": a.id,
            "title": a.title,
            "date": a.appointment_date.isoformat(),
            "time": a.appointment_time.isoformat() if a.appointment_time else None,
            "duration_minutes": a.duration_minutes,
            "type": a.appointment_type,
            "contact_id": a.contact_id,
            "contact_name": contact.name if contact else None,
            "assigned_to_user_id": a.assigned_to_user_id,
        }
        for a, contact in rows
    ]


def _briefing_overdue_followups(
    db: Session, today: date
) -> List[Dict[str, Any]]:
    """Contacts with an open estimate ('sent' or 'viewed') and no recent
    note/activity in OVERDUE_FOLLOWUP_DAYS+ days."""
    from app.models.job import Job

    cutoff_dt = datetime.combine(
        today - timedelta(days=OVERDUE_FOLLOWUP_DAYS),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    pairs = (
        db.query(Contact, Estimate)
        .join(Job, Job.contact_id == Contact.id)
        .join(Estimate, Estimate.job_id == Job.id)
        .filter(Estimate.status.in_(["sent", "viewed"]))
        .all()
    )

    out: List[Dict[str, Any]] = []
    seen_contact_ids = set()
    for contact, estimate in pairs:
        if contact.id in seen_contact_ids:
            continue
        latest_note = (
            db.query(Note.created_at)
            .filter(Note.entity_type == "contact")
            .filter(Note.entity_id == contact.id)
            .order_by(Note.created_at.desc())
            .first()
        )
        last_touch = latest_note[0] if latest_note else estimate.created_at
        if last_touch and last_touch >= cutoff_dt:
            continue
        seen_contact_ids.add(contact.id)
        out.append(
            {
                "contact_id": contact.id,
                "contact_name": contact.name,
                "contact_phone": contact.phone,
                "estimate_id": estimate.id,
                "estimate_total": str(estimate.total or 0),
                "last_activity": (
                    last_touch.isoformat() if last_touch else None
                ),
            }
        )
    return out


def _briefing_unsigned_estimates(
    db: Session, now_local: datetime
) -> Dict[str, List[Dict[str, Any]]]:
    """Group 'sent' estimates by signal: viewed-but-not-signed, not viewed
    yet, or aging > 5 days."""
    from app.models.job import Job

    pairs = (
        db.query(Estimate, Contact)
        .outerjoin(Job, Job.id == Estimate.job_id)
        .outerjoin(Contact, Contact.id == Job.contact_id)
        .filter(Estimate.status.in_(["sent", "viewed"]))
        .all()
    )
    aging_cutoff = now_local - timedelta(days=AGING_ESTIMATE_DAYS)
    out: Dict[str, List[Dict[str, Any]]] = {
        "viewed_not_signed": [],
        "not_viewed": [],
        "aging_over_5_days": [],
    }
    for est, contact in pairs:
        viewed = est.status == "viewed" or (
            db.query(EstimateStatusHistory)
            .filter(EstimateStatusHistory.estimate_id == est.id)
            .filter(EstimateStatusHistory.status == "viewed")
            .first()
            is not None
        )
        row = {
            "id": est.id,
            "name": est.name or f"Estimate #{est.id}",
            "status": est.status,
            "total": str(est.total or 0),
            "created_at": (
                est.created_at.isoformat() if est.created_at else None
            ),
            "contact_id": contact.id if contact else None,
            "contact_name": contact.name if contact else None,
        }
        created_at_aware = est.created_at
        if (
            created_at_aware
            and created_at_aware.tzinfo
            and created_at_aware < aging_cutoff
        ):
            out["aging_over_5_days"].append(row)
            continue
        if viewed:
            out["viewed_not_signed"].append(row)
        else:
            out["not_viewed"].append(row)
    return out


def _briefing_stale_leads(db: Session, today: date) -> List[Dict[str, Any]]:
    """Contacts in the Leads pipeline with no activity in 14+ days."""
    from app.models.job import Job

    leads_pipeline = (
        db.query(Pipeline).filter(Pipeline.slug == "leads").first()
    )
    if leads_pipeline is None:
        return []
    cutoff_dt = datetime.combine(
        today - timedelta(days=STALE_LEAD_DAYS),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    contacts = (
        db.query(Contact)
        .filter(Contact.pipeline_id == leads_pipeline.id)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for c in contacts:
        latest_note = (
            db.query(Note.created_at)
            .filter(Note.entity_type == "contact")
            .filter(Note.entity_id == c.id)
            .order_by(Note.created_at.desc())
            .first()
        )
        last_touch = latest_note[0] if latest_note else c.created_at
        if last_touch and last_touch >= cutoff_dt:
            continue
        biggest = (
            db.query(Estimate.total)
            .join(Job, Job.id == Estimate.job_id)
            .filter(Job.contact_id == c.id)
            .order_by(Estimate.total.desc().nullslast())
            .first()
        )
        out.append(
            {
                "contact_id": c.id,
                "contact_name": c.name,
                "contact_phone": c.phone,
                "lead_source": c.lead_source,
                "estimate_value": str(biggest[0]) if biggest and biggest[0] else "0",
                "last_activity": last_touch.isoformat() if last_touch else None,
            }
        )
    out.sort(key=lambda r: Decimal(r["estimate_value"] or "0"), reverse=True)
    return out


def _briefing_recent_customer_actions(
    db: Session, now_local: datetime
) -> List[Dict[str, Any]]:
    cutoff = now_local - timedelta(hours=RECENT_ACTION_HOURS)
    out: List[Dict[str, Any]] = []
    history = (
        db.query(EstimateStatusHistory)
        .filter(EstimateStatusHistory.changed_at >= cutoff)
        .filter(EstimateStatusHistory.status.in_(["viewed", "approved"]))
        .order_by(EstimateStatusHistory.changed_at.desc())
        .all()
    )
    for h in history:
        out.append(
            {
                "type": f"estimate_{h.status}",
                "estimate_id": h.estimate_id,
                "at": h.changed_at.isoformat() if h.changed_at else None,
                "actor": h.changed_by_name,
            }
        )
    payments = (
        db.query(Payment)
        .filter(Payment.created_at >= cutoff)
        .order_by(Payment.created_at.desc())
        .all()
    )
    for p in payments:
        out.append(
            {
                "type": "payment",
                "invoice_id": p.invoice_id,
                "amount": str(p.amount),
                "method": p.method,
                "at": p.created_at.isoformat() if p.created_at else None,
            }
        )
    return out


def _briefing_overnight_ai_actions(
    db: Session, now_local: datetime
) -> List[Dict[str, Any]]:
    """AIAction rows created since the last 7am Indiana time."""
    today = now_local.date()
    seven_am = datetime.combine(
        today, datetime.min.time(), tzinfo=INDIANA_TZ
    ).replace(hour=7)
    if now_local < seven_am:
        seven_am = seven_am - timedelta(days=1)
    rows = (
        db.query(AIAction)
        .filter(AIAction.created_at >= seven_am)
        .order_by(AIAction.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "status": r.status,
            "contact_id": r.contact_id,
            "estimate_id": r.estimate_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
