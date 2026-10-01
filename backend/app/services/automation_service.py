"""Sprint 19a — pipeline automation engine.

Service layer responsibilities:

- Enroll contacts in sequences when trigger events fire (with eligibility checks)
- Advance enrolled contacts through their sequence steps on schedule
- Render templated message bodies with contact/estimate tokens
- Send via SMS (Twilio) or email (SMTP), respecting kill switches
- Stop sequences on reply, stage change, manual stop, or opt-out

The scheduler (Sprint 19b) calls ``process_pending_steps`` periodically; this
module only deals with eligibility, rendering, and per-step bookkeeping.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.automation import (
    AutomationEnrollment,
    AutomationLog,
    AutomationSequence,
    AutomationStep,
)
from app.models.contact import Contact
from app.services import sms_service

logger = logging.getLogger("legacy_crm.automation")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _split_name(full_name: Optional[str]) -> Tuple[str, str]:
    if not full_name:
        return "", ""
    parts = full_name.strip().split(None, 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first, last


def _company_phone() -> str:
    return os.environ.get("AI_COMPANY_PHONE", "(765) 555-0100")


def _portal_base_url() -> str:
    return os.environ.get("PORTAL_BASE_URL", "").rstrip("/")


def _review_link() -> str:
    return os.environ.get("REVIEW_LINK", "(review link not configured)")


def _has_active_steps(sequence: AutomationSequence) -> bool:
    return any(step.is_active for step in sequence.steps)


def _step_for_order(
    sequence: AutomationSequence, step_order: int
) -> Optional[AutomationStep]:
    for step in sequence.steps:
        if step.step_order == step_order and step.is_active:
            return step
    return None


def _next_active_step(
    sequence: AutomationSequence, after_order: int
) -> Optional[AutomationStep]:
    candidates = sorted(
        (s for s in sequence.steps if s.is_active and s.step_order > after_order),
        key=lambda s: s.step_order,
    )
    return candidates[0] if candidates else None


def _first_active_step(sequence: AutomationSequence) -> Optional[AutomationStep]:
    candidates = sorted(
        (s for s in sequence.steps if s.is_active),
        key=lambda s: s.step_order,
    )
    return candidates[0] if candidates else None


def _sequence_has_sms_step(sequence: AutomationSequence) -> bool:
    return any(step.is_active and step.channel == "sms" for step in sequence.steps)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------
def render_template(
    template: str,
    contact: Optional[Contact] = None,
    estimate: Optional[Any] = None,
    **overrides: Any,
) -> str:
    """Render an automation template body / subject.

    Supported tokens (always available, default to empty string when unknown):
      {first_name}, {last_name}, {full_name}, {company_name},
      {phone}, {rep_name}, {service_type}, {estimate_total},
      {estimate_link}, {review_link}, {company_phone}

    Extra keyword arguments override these defaults.
    """
    first, last = _split_name(getattr(contact, "name", None) if contact else None)

    rep_name = ""
    if estimate is not None:
        assigned = getattr(estimate, "assigned_to", None)
        if assigned is not None:
            rep_name = (getattr(assigned, "full_name", "") or "").strip()

    service_type = ""
    estimate_total = ""
    estimate_link = ""
    if estimate is not None:
        wt = getattr(estimate, "work_type", None)
        if wt:
            service_type = str(wt).replace("_", " ").title()
        total_val = getattr(estimate, "total", None)
        if total_val is not None:
            try:
                estimate_total = f"${float(total_val):,.2f}"
            except (TypeError, ValueError):
                estimate_total = str(total_val)

        token_rows = getattr(estimate, "tokens", None)
        token_str: Optional[str] = None
        if token_rows:
            try:
                token_str = sorted(
                    token_rows, key=lambda t: t.created_at, reverse=True
                )[0].token
            except Exception:
                token_str = None
        base = _portal_base_url()
        if token_str and base:
            estimate_link = f"{base}/portal/estimate/{token_str}"
        elif token_str:
            estimate_link = f"/portal/estimate/{token_str}"

    tokens: Dict[str, str] = {
        "first_name": first,
        "last_name": last,
        "full_name": (getattr(contact, "name", "") or "") if contact else "",
        "company_name": (getattr(contact, "company", "") or "") if contact else "",
        "phone": (getattr(contact, "phone", "") or "") if contact else "",
        "rep_name": rep_name,
        "service_type": service_type,
        "estimate_total": estimate_total,
        "estimate_link": estimate_link,
        "review_link": _review_link(),
        "company_phone": _company_phone(),
    }
    for key, value in overrides.items():
        tokens[key] = "" if value is None else str(value)

    out = template or ""
    for key, value in tokens.items():
        out = out.replace("{" + key + "}", value)
    return out


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------
class EnrollmentResult:
    """Lightweight return type for enroll_contact.

    enrollment: The AutomationEnrollment row (or None when blocked).
    reason: Human-readable reason when blocked.
    """

    __slots__ = ("enrollment", "reason")

    def __init__(
        self,
        enrollment: Optional[AutomationEnrollment],
        reason: Optional[str] = None,
    ) -> None:
        self.enrollment = enrollment
        self.reason = reason


def enroll_contact(
    db: Session, contact_id: int, sequence_id: int
) -> EnrollmentResult:
    """Enroll a contact in a sequence.

    Blocks (returns ``EnrollmentResult(None, reason=...)``) when:
      - the contact does not exist
      - ``contact.automations_enabled`` is False
      - the contact has opted out of SMS and the sequence has SMS steps
      - the sequence is inactive
      - the sequence has no active steps
      - an active enrollment already exists for this (sequence, contact)
    """
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        return EnrollmentResult(None, "contact not found")
    if not contact.automations_enabled:
        return EnrollmentResult(None, "automations disabled for contact")

    sequence = (
        db.query(AutomationSequence)
        .filter(AutomationSequence.id == sequence_id)
        .first()
    )
    if not sequence:
        return EnrollmentResult(None, "sequence not found")
    if not sequence.is_active:
        return EnrollmentResult(None, "sequence inactive")
    if contact.sms_opt_out and _sequence_has_sms_step(sequence):
        return EnrollmentResult(None, "contact has opted out of SMS")

    first_step = _first_active_step(sequence)
    if not first_step:
        return EnrollmentResult(None, "sequence has no active steps")

    existing = (
        db.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.sequence_id == sequence_id,
            AutomationEnrollment.contact_id == contact_id,
            AutomationEnrollment.status == "active",
        )
        .first()
    )
    if existing:
        return EnrollmentResult(None, "active enrollment already exists")

    next_step_at = _utcnow() + timedelta(minutes=first_step.delay_minutes)
    enrollment = AutomationEnrollment(
        sequence_id=sequence_id,
        contact_id=contact_id,
        current_step_order=first_step.step_order,
        status="active",
        next_step_at=next_step_at,
    )
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError:
        # Unique (sequence_id, contact_id) constraint — a prior enrollment
        # row exists (possibly stopped or completed). v1 treats this as a
        # block; re-enrollment requires manual cleanup or a future schema
        # change that scopes the uniqueness to active rows only.
        db.rollback()
        return EnrollmentResult(None, "enrollment row already exists for contact")
    db.refresh(enrollment)
    return EnrollmentResult(enrollment)


def stop_enrollment(
    db: Session,
    enrollment_id: int,
    reason: str,
    detail: Optional[str] = None,
) -> Optional[AutomationEnrollment]:
    """Mark an enrollment as stopped. ``reason`` is one of:

    ``reply``, ``stage_change``, ``manual``, ``optout``.

    Already-completed or already-stopped enrollments are returned unchanged.
    """
    enrollment = (
        db.query(AutomationEnrollment)
        .filter(AutomationEnrollment.id == enrollment_id)
        .first()
    )
    if not enrollment:
        return None
    if enrollment.status != "active":
        return enrollment

    status_map = {
        "reply": "stopped_reply",
        "stage_change": "stopped_stage_change",
        "manual": "stopped_manual",
        "optout": "stopped_optout",
    }
    enrollment.status = status_map.get(reason, "stopped_manual")
    enrollment.stopped_at = _utcnow()
    enrollment.stopped_reason = detail or reason
    enrollment.next_step_at = None
    db.commit()
    db.refresh(enrollment)
    return enrollment


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------
def _send_step(
    db: Session,
    enrollment: AutomationEnrollment,
    step: AutomationStep,
    contact: Contact,
) -> AutomationLog:
    """Send a single step and return the AutomationLog row.

    The log row is always created, even on skip / failure, so the engine has a
    full audit trail. The enrollment is not advanced here — that happens in
    ``process_pending_steps`` after this call returns.
    """
    body = render_template(step.template_body, contact)
    subject = (
        render_template(step.template_subject, contact)
        if step.template_subject
        else None
    )

    log = AutomationLog(
        enrollment_id=enrollment.id,
        step_id=step.id,
        channel=step.channel,
        rendered_body=body,
        rendered_subject=subject,
        status="pending",
    )
    db.add(log)
    db.flush()

    if step.channel == "sms":
        if not sms_service.sms_enabled():
            log.status = "skipped"
            log.error_message = "SMS_ENABLED is false"
            db.commit()
            db.refresh(log)
            return log
        if not contact.phone or contact.sms_opt_out:
            log.status = "skipped"
            log.error_message = (
                "contact has no phone"
                if not contact.phone
                else "contact has opted out"
            )
            db.commit()
            db.refresh(log)
            return log
        try:
            sms_msg = sms_service.send_sms(
                db, contact.id, body, triggered_by="automation"
            )
            if sms_msg.status == "failed":
                log.status = "failed"
                log.error_message = sms_msg.status_detail
            else:
                log.status = "sent"
                log.sent_at = _utcnow()
        except ValueError as exc:
            log.status = "failed"
            log.error_message = str(exc)[:1000]
        db.commit()
        db.refresh(log)
        return log

    if step.channel == "email":
        if not contact.email:
            log.status = "skipped"
            log.error_message = "contact has no email"
            db.commit()
            db.refresh(log)
            return log
        try:
            from app.services import email_service

            email_service.send_email(
                to_email=contact.email,
                subject=subject or "",
                html_body=body,
            )
            log.status = "sent"
            log.sent_at = _utcnow()
        except Exception as exc:  # pragma: no cover — exercised via mocks
            log.status = "failed"
            log.error_message = str(exc)[:1000]
            logger.exception(
                "automation email send failed for enrollment %s", enrollment.id
            )
        db.commit()
        db.refresh(log)
        return log

    # Unknown channel — record and move on.
    log.status = "failed"
    log.error_message = f"unknown channel: {step.channel}"
    db.commit()
    db.refresh(log)
    return log


def _advance_enrollment(
    db: Session,
    enrollment: AutomationEnrollment,
    sequence: AutomationSequence,
    just_ran_step: AutomationStep,
) -> None:
    """Move an enrollment to its next active step, or complete it."""
    next_step = _next_active_step(sequence, just_ran_step.step_order)
    if next_step is None:
        enrollment.status = "completed"
        enrollment.completed_at = _utcnow()
        enrollment.next_step_at = None
    else:
        enrollment.current_step_order = next_step.step_order
        enrollment.next_step_at = _utcnow() + timedelta(
            minutes=next_step.delay_minutes
        )
    db.commit()


def process_pending_steps(
    db: Session, now: Optional[datetime] = None
) -> List[AutomationLog]:
    """Run all enrollments whose next step is due.

    Returns the list of AutomationLog rows created in this pass. Safe to call
    repeatedly — a step that has already been advanced past is not re-run.
    """
    cutoff = now or _utcnow()
    pending = (
        db.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.status == "active",
            AutomationEnrollment.next_step_at.isnot(None),
            AutomationEnrollment.next_step_at <= cutoff,
        )
        .all()
    )

    logs: List[AutomationLog] = []
    for enrollment in pending:
        sequence = enrollment.sequence
        contact = enrollment.contact
        if sequence is None or contact is None:
            continue
        if not sequence.is_active:
            # Sequence paused after enrollment — leave the enrollment as-is
            # so it picks back up when the sequence is re-activated.
            continue
        if not contact.automations_enabled:
            stop_enrollment(
                db, enrollment.id, "manual", "automations disabled for contact"
            )
            continue

        step = _step_for_order(sequence, enrollment.current_step_order)
        if step is None:
            # Current step was deactivated — try to find a later active step.
            step = _next_active_step(
                sequence, enrollment.current_step_order - 1
            )
            if step is None:
                enrollment.status = "completed"
                enrollment.completed_at = _utcnow()
                enrollment.next_step_at = None
                db.commit()
                continue
            enrollment.current_step_order = step.step_order

        log = _send_step(db, enrollment, step, contact)
        logs.append(log)
        _advance_enrollment(db, enrollment, sequence, step)

    return logs


# ---------------------------------------------------------------------------
# Trigger handlers
# ---------------------------------------------------------------------------
def _enroll_for_matching_sequences(
    db: Session,
    contact_id: int,
    trigger_type: str,
    matches_config,
) -> List[AutomationEnrollment]:
    """Find active sequences with the given trigger and enroll the contact
    in each one whose ``trigger_config`` matches ``matches_config(config)``.
    """
    sequences = (
        db.query(AutomationSequence)
        .filter(
            AutomationSequence.trigger_type == trigger_type,
            AutomationSequence.is_active.is_(True),
        )
        .all()
    )
    enrolled: List[AutomationEnrollment] = []
    for seq in sequences:
        config = seq.trigger_config or {}
        try:
            if not matches_config(config):
                continue
        except Exception:
            continue
        result = enroll_contact(db, contact_id, seq.id)
        if result.enrollment is not None:
            enrolled.append(result.enrollment)
    return enrolled


def on_contact_created(db: Session, contact_id: int) -> List[AutomationEnrollment]:
    """Trigger: new contact lands. Enrolls in any ``contact_created`` sequence."""
    return _enroll_for_matching_sequences(
        db, contact_id, "contact_created", lambda _cfg: True
    )


def on_estimate_sent(
    db: Session, contact_id: int, estimate_id: int
) -> List[AutomationEnrollment]:
    """Trigger: estimate sent. Enrolls in any ``estimate_sent`` sequence."""
    return _enroll_for_matching_sequences(
        db, contact_id, "estimate_sent", lambda _cfg: True
    )


def on_estimate_viewed(
    db: Session, contact_id: int, estimate_id: int
) -> List[AutomationEnrollment]:
    """Trigger: customer opened the portal. Wired here for forward compat."""
    return _enroll_for_matching_sequences(
        db, contact_id, "estimate_viewed", lambda _cfg: True
    )


def on_pipeline_stage_change(
    db: Session,
    contact_id: int,
    pipeline_slug: str,
    from_stage_id: Optional[int],
    to_stage_id: Optional[int],
) -> List[AutomationEnrollment]:
    """Trigger: contact moved between pipeline stages.

    Matches sequences whose ``trigger_config`` declares ``pipeline_slug`` and
    ``to_stage_id`` matching the move. Also handles the ``job_completed``
    convenience trigger for moves into a Complete-style stage.
    """
    enrolled: List[AutomationEnrollment] = []

    def matches_stage(cfg: Dict[str, Any]) -> bool:
        if pipeline_slug and cfg.get("pipeline_slug") not in (
            None,
            pipeline_slug,
        ):
            return False
        target = cfg.get("to_stage_id")
        if target is None:
            return True
        try:
            return int(target) == int(to_stage_id) if to_stage_id is not None else False
        except (TypeError, ValueError):
            return False

    enrolled.extend(
        _enroll_for_matching_sequences(
            db, contact_id, "pipeline_stage_change", matches_stage
        )
    )

    def matches_job_complete(cfg: Dict[str, Any]) -> bool:
        # If config specifies a stage, honor it; otherwise accept any move.
        if cfg.get("pipeline_slug") and cfg["pipeline_slug"] != pipeline_slug:
            return False
        target = cfg.get("to_stage_id")
        if target is None:
            return True
        try:
            return int(target) == int(to_stage_id) if to_stage_id is not None else False
        except (TypeError, ValueError):
            return False

    enrolled.extend(
        _enroll_for_matching_sequences(
            db, contact_id, "job_completed", matches_job_complete
        )
    )
    return enrolled


def on_job_completed(
    db: Session, contact_id: int, job_id: Optional[int] = None
) -> List[AutomationEnrollment]:
    """Trigger: a job moved to the Complete stage.

    Provided as an explicit hook for callers that don't have stage IDs handy.
    The pipeline-stage-change path is the more common entry point.
    """
    return _enroll_for_matching_sequences(
        db, contact_id, "job_completed", lambda _cfg: True
    )


# ---------------------------------------------------------------------------
# Stop-condition checks
# ---------------------------------------------------------------------------
def check_reply_stop(db: Session, contact_id: int) -> List[AutomationEnrollment]:
    """Called when a contact replies (inbound SMS / email).

    Stops active enrollments whose *current* step has ``stop_on_reply=True``.
    """
    enrollments = (
        db.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.contact_id == contact_id,
            AutomationEnrollment.status == "active",
        )
        .all()
    )
    stopped: List[AutomationEnrollment] = []
    for enrollment in enrollments:
        sequence = enrollment.sequence
        if not sequence:
            continue
        step = _step_for_order(sequence, enrollment.current_step_order)
        if step is None or not step.stop_on_reply:
            continue
        stop_enrollment(db, enrollment.id, "reply", "contact replied")
        stopped.append(enrollment)
    return stopped


def check_stage_change_stop(
    db: Session, contact_id: int
) -> List[AutomationEnrollment]:
    """Called after a pipeline stage change.

    Stops active enrollments whose *current* step has ``stop_on_stage_change=True``.
    """
    enrollments = (
        db.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.contact_id == contact_id,
            AutomationEnrollment.status == "active",
        )
        .all()
    )
    stopped: List[AutomationEnrollment] = []
    for enrollment in enrollments:
        sequence = enrollment.sequence
        if not sequence:
            continue
        step = _step_for_order(sequence, enrollment.current_step_order)
        if step is None or not step.stop_on_stage_change:
            continue
        stop_enrollment(db, enrollment.id, "stage_change", "contact moved stages")
        stopped.append(enrollment)
    return stopped


def check_optout_stop(db: Session, contact_id: int) -> List[AutomationEnrollment]:
    """Called when a contact opts out of SMS.

    Stops *every* active enrollment that has at least one SMS step (since the
    contact can no longer receive those messages). Email-only sequences are
    left running.
    """
    enrollments = (
        db.query(AutomationEnrollment)
        .filter(
            AutomationEnrollment.contact_id == contact_id,
            AutomationEnrollment.status == "active",
        )
        .all()
    )
    stopped: List[AutomationEnrollment] = []
    for enrollment in enrollments:
        sequence = enrollment.sequence
        if not sequence:
            continue
        if not _sequence_has_sms_step(sequence):
            continue
        stop_enrollment(db, enrollment.id, "optout", "contact opted out of SMS")
        stopped.append(enrollment)
    return stopped
