"""Event dispatcher: builds CRM context for an event, calls the configured
AI provider, and persists the result to ``ai_actions``.

Designed to be safe to call from any path. Failures are logged but never
raised — AI is optional. Hooks should still wrap dispatch in a top-level
try/except as a belt-and-suspenders measure.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.ai_action import AIAction
from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.estimate_line_item import EstimateLineItem
from app.models.estimate_status_history import EstimateStatusHistory
from app.models.job import Job
from app.models.note import Note
from app.services.ai_prompts import render_prompt
from app.services.ai_provider import AIProvider, AIResponse, get_provider

logger = logging.getLogger("legacy_crm.ai")


# ---------- Context builders ----------


def _company_context() -> Dict[str, Any]:
    return {
        "company_name": settings.ai_company_name,
        "company_phone": settings.ai_company_phone,
    }


def _contact_basics(contact: Contact) -> Dict[str, Any]:
    full_address_parts = [
        contact.address,
        f"{contact.city}, {contact.state} {contact.zip}".strip(", "),
    ]
    full_address = ", ".join(p for p in full_address_parts if p and p.strip())
    return {
        "contact_name": contact.name,
        "contact_phone": contact.phone or "",
        "contact_email": contact.email or "",
        "contact_address": contact.address or "",
        "full_address": full_address or contact.address or "",
        "lead_source": contact.lead_source or "",
        "client_type": contact.client_type or "",
    }


def _format_line_items(estimate: Estimate) -> str:
    lines = []
    for li in sorted(
        estimate.line_items or [], key=lambda li: li.sort_order or 0
    ):
        qty = li.qty or 0
        unit = li.unit_price or 0
        total = li.line_total or 0
        lines.append(
            f"- {li.description}  ({qty} × ${unit} = ${total})"
        )
    return "\n".join(lines) or "(no line items)"


def _all_notes_for_contact(db: Session, contact_id: int) -> str:
    estimate_ids = [
        eid
        for (eid,) in db.query(Estimate.id)
        .join(Job, Estimate.job_id == Job.id)
        .filter(Job.contact_id == contact_id)
        .all()
    ]

    rows = (
        db.query(Note)
        .filter(
            (
                (Note.entity_type == "contact")
                & (Note.entity_id == contact_id)
            )
            | (
                (Note.entity_type == "estimate")
                & (Note.entity_id.in_(estimate_ids or [-1]))
            )
        )
        .order_by(Note.created_at.desc())
        .limit(20)
        .all()
    )
    if not rows:
        return "(none)"
    return "\n".join(
        f"- [{n.note_type}] {(n.content or '').strip()[:300]}" for n in rows
    )


def _estimates_summary_for_contact(db: Session, contact_id: int) -> str:
    estimates = (
        db.query(Estimate)
        .join(Job, Estimate.job_id == Job.id)
        .filter(Job.contact_id == contact_id)
        .order_by(Estimate.created_at.desc())
        .limit(10)
        .all()
    )
    if not estimates:
        return "(no estimates yet)"
    out = []
    for est in estimates:
        out.append(
            f"- EST-{est.id:04d} ({est.status}) "
            f"${est.total or Decimal('0')} — {est.name or 'Untitled'}"
        )
    return "\n".join(out)


def _activity_summary_for_contact(db: Session, contact_id: int) -> str:
    history = (
        db.query(EstimateStatusHistory)
        .join(Estimate, EstimateStatusHistory.estimate_id == Estimate.id)
        .join(Job, Estimate.job_id == Job.id)
        .filter(Job.contact_id == contact_id)
        .order_by(EstimateStatusHistory.changed_at.desc())
        .limit(10)
        .all()
    )
    if not history:
        return "(no recent activity)"
    return "\n".join(
        f"- {h.changed_at:%Y-%m-%d}: estimate marked {h.status}" for h in history
    )


# ---------- Public dispatch ----------


def build_context(
    *,
    event_type: str,
    db: Session,
    contact_id: Optional[int] = None,
    estimate_id: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble the prompt context for an event."""
    ctx: Dict[str, Any] = dict(_company_context())

    contact: Optional[Contact] = None
    estimate: Optional[Estimate] = None

    if contact_id is not None:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()

    if estimate_id is not None:
        estimate = (
            db.query(Estimate)
            .options(
                joinedload(Estimate.line_items),
                joinedload(Estimate.job).joinedload(Job.contact),
            )
            .filter(Estimate.id == estimate_id)
            .first()
        )
        if contact is None and estimate and estimate.job and estimate.job.contact:
            contact = estimate.job.contact

    if contact is not None:
        ctx.update(_contact_basics(contact))
        ctx["contact_notes"] = (extra or {}).get("contact_notes") or ""
        if event_type == "pre_visit_summary":
            ctx["estimates_summary"] = _estimates_summary_for_contact(
                db, contact.id
            )
            ctx["all_notes"] = _all_notes_for_contact(db, contact.id)
            ctx["activity_summary"] = _activity_summary_for_contact(
                db, contact.id
            )

    if estimate is not None:
        ctx["estimate_name"] = estimate.name or f"Estimate #{estimate.id}"
        ctx["estimate_total"] = f"${estimate.total or Decimal('0')}"
        ctx["line_items_formatted"] = _format_line_items(estimate)

    if event_type == "lead_created" and contact is not None:
        ctx["service_interest"] = (
            (extra or {}).get("service_interest")
            or contact.lead_source
            or "general inquiry"
        )

    if event_type == "follow_up_overdue":
        ctx["days_since_activity"] = (extra or {}).get("days_since_activity", 0)
        ctx["last_activity_date"] = (extra or {}).get("last_activity_date", "")

    if event_type == "job_completed":
        ctx["work_description"] = (
            (extra or {}).get("work_description")
            or (estimate.name if estimate else "")
        )
        ctx["completion_date"] = (extra or {}).get("completion_date", "")
        ctx["google_review_link"] = (extra or {}).get(
            "google_review_link", "https://g.page/r/legacy-roofing/review"
        )

    if event_type == "estimate_approved":
        ctx["customer_notes"] = (extra or {}).get("customer_notes", "")
        ctx["internal_notes"] = (extra or {}).get("internal_notes", "")

    if extra:
        for k, v in extra.items():
            ctx.setdefault(k, v)

    return ctx


def dispatch(
    *,
    db: Session,
    event_type: str,
    contact_id: Optional[int] = None,
    estimate_id: Optional[int] = None,
    user_id: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
    provider: Optional[AIProvider] = None,
) -> Optional[AIAction]:
    """Run the full event → context → LLM → persist pipeline.

    Returns the persisted ``AIAction`` row (with status reflecting success
    or failure), or ``None`` if AI is globally disabled.
    """
    if not settings.ai_enabled:
        logger.info("AI dispatch skipped — AI_ENABLED=false (event=%s)", event_type)
        return None

    try:
        ctx = build_context(
            event_type=event_type,
            db=db,
            contact_id=contact_id,
            estimate_id=estimate_id,
            extra=extra,
        )
        system_prompt, user_prompt = render_prompt(event_type, ctx)
    except Exception as exc:
        logger.warning(
            "AI dispatch failed during context/prompt build for %s: %s",
            event_type,
            exc,
        )
        return _persist_failure(
            db=db,
            event_type=event_type,
            contact_id=contact_id,
            estimate_id=estimate_id,
            user_id=user_id,
            provider_name="error",
            model="",
            system_prompt="",
            user_prompt="",
            error=str(exc),
        )

    active = provider or get_provider()
    response: AIResponse
    try:
        response = active.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    except Exception as exc:  # belt-and-suspenders; providers shouldn't raise
        logger.warning("AI provider raised: %s", exc)
        response = AIResponse(
            content="",
            provider=getattr(active, "name", "unknown"),
            model=getattr(active, "model", ""),
            success=False,
            error=str(exc),
        )

    record = AIAction(
        id=uuid.uuid4().hex,
        event_type=event_type,
        contact_id=contact_id,
        estimate_id=estimate_id,
        provider=response.provider,
        model=response.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output=response.content,
        tokens_used=response.tokens_used or None,
        duration_ms=response.duration_ms or None,
        status="completed" if response.success else "failed",
        error=response.error,
        created_by=user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _persist_failure(
    *,
    db: Session,
    event_type: str,
    contact_id: Optional[int],
    estimate_id: Optional[int],
    user_id: Optional[int],
    provider_name: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    error: str,
) -> AIAction:
    record = AIAction(
        id=uuid.uuid4().hex,
        event_type=event_type,
        contact_id=contact_id,
        estimate_id=estimate_id,
        provider=provider_name,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output="",
        status="failed",
        error=error,
        created_by=user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def safe_dispatch(*args, **kwargs) -> Optional[AIAction]:
    """Wrapper that swallows all exceptions — for fire-and-forget hooks
    where the user-facing operation has already committed and we must
    never raise."""
    try:
        return dispatch(*args, **kwargs)
    except Exception as exc:
        logger.exception("safe_dispatch swallowed exception: %s", exc)
        return None
