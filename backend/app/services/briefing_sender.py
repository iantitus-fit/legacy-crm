"""Orchestrator for the daily morning briefing email.

send_morning_briefing(db, recipient, dry_run) is the single public entrypoint.
It fetches the briefing context, builds per-recipient views, renders the
HTML and subject, and sends via the existing SMTP utility — or returns the
rendered HTML if dry_run=True.
"""
import logging
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.ai_chat import get_briefing_context
from app.services.briefing_filters import marcus_view, dale_view
from app.services.briefing_renderer import (
    render_marcus_email,
    render_dale_email,
    render_subject,
)
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

VALID_RECIPIENTS = ("dale", "marcus", "all")


def _resolve_user_id(db: Session) -> int:
    """The briefing endpoint requires a user_id (for task-assignment filtering).
    Use the first active admin as the system user for scheduled sends.
    """
    from app.models.user import User

    admin = (
        db.query(User)
        .filter(User.role == "admin", User.is_active.is_(True))
        .order_by(User.id.asc())
        .first()
    )
    if admin is None:
        raise RuntimeError("No admin user available — cannot build briefing")
    return admin.id


def _build_view(recipient: str, briefing_data: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    yesterday = today - timedelta(days=1)
    if recipient == "dale":
        return dale_view(briefing_data, briefing_date=today.isoformat(),
                         yesterday=yesterday.isoformat())
    if recipient == "marcus":
        return marcus_view(briefing_data, briefing_date=today.isoformat(),
                         yesterday=yesterday.isoformat())
    raise ValueError(f"unknown recipient: {recipient}")


def _render_for(recipient: str, view: Dict[str, Any]) -> tuple:
    if recipient == "dale":
        return render_dale_email(view), render_subject(view)
    if recipient == "marcus":
        return render_marcus_email(view), render_subject(view)
    raise ValueError(f"unknown recipient: {recipient}")


def send_morning_briefing(
    db: Session,
    recipient: str = "all",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Send (or preview) the morning briefing.

    Args:
        db: SQLAlchemy session.
        recipient: "dale", "marcus", or "all".
        dry_run: if True, render but don't send. Returns the HTML in previews.

    Returns dict with: sent_to (List[str]), skipped (List[dict]),
    previews (List[dict] with recipient/subject/html/to).
    """
    if recipient not in VALID_RECIPIENTS:
        raise ValueError(f"recipient must be one of {VALID_RECIPIENTS}")

    targets = ["dale", "marcus"] if recipient == "all" else [recipient]

    user_id = _resolve_user_id(db)
    briefing_data = get_briefing_context(db=db, user_id=user_id)

    sent_to: List[str] = []
    skipped: List[Dict[str, Any]] = []
    previews: List[Dict[str, Any]] = []

    for r in targets:
        env_key = f"BRIEFING_EMAIL_{r.upper()}"
        to_addr = os.environ.get(env_key, "").strip()
        view = _build_view(r, briefing_data)
        html, subject = _render_for(r, view)
        if not to_addr:
            logger.warning(
                "Skipping %s briefing — %s env var not set", r, env_key,
            )
            skipped.append({"recipient": r, "reason": f"{env_key} not set"})
            continue
        if dry_run:
            previews.append({
                "recipient": r, "to": to_addr,
                "subject": subject, "html": html,
            })
            continue
        try:
            send_email(to_addr, subject, html)
            sent_to.append(to_addr)
            previews.append({
                "recipient": r, "to": to_addr,
                "subject": subject, "html": html,
            })
            logger.info("Sent %s briefing to %s — %s", r, to_addr, subject)
        except Exception as e:
            logger.exception("Failed to send %s briefing", r)
            skipped.append({"recipient": r, "reason": f"send_error: {e}"})

    return {
        "sent_to": sent_to,
        "skipped": skipped,
        "previews": previews if dry_run else [
            {"recipient": p["recipient"], "to": p["to"], "subject": p["subject"]}
            for p in previews
        ],
        "dry_run": dry_run,
    }
