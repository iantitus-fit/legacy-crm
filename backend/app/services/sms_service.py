"""SMS service — Twilio integration, send/receive, auto-respond.

For v1, Twilio credentials are read from environment variables (SMS_ENABLED,
TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER). The sms_config
table holds templates, business hours, and toggles. Credential columns on
sms_config exist for future use when config is managed via UI.

SMS_ENABLED=false is the kill switch: all send operations become no-ops.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.sms import SmsConfig, SmsMessage
from app.services.phone_utils import (
    format_for_display,
    match_phone,
    normalize_to_e164,
)

logger = logging.getLogger("legacy_crm.sms")


# ---------------------------------------------------------------------------
# Backwards-compat alias for the spec naming
# ---------------------------------------------------------------------------
def normalize_phone(phone: Optional[str]) -> Optional[str]:
    return normalize_to_e164(phone)


# ---------------------------------------------------------------------------
# Config + Twilio client
# ---------------------------------------------------------------------------
def sms_enabled() -> bool:
    val = os.environ.get("SMS_ENABLED", "false").strip().lower()
    return val in ("1", "true", "yes", "on")


def ensure_sms_config(db: Session) -> SmsConfig:
    """Return the singleton sms_config row, creating it with defaults if needed."""
    config = db.query(SmsConfig).first()
    if config:
        return config
    config = SmsConfig()
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def get_twilio_credentials(config: SmsConfig) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve Twilio (account_sid, auth_token, from_number).

    Env vars take precedence; sms_config row is fallback for future UI-managed
    config.
    """
    sid = os.environ.get("TWILIO_ACCOUNT_SID") or config.twilio_account_sid
    token = (
        os.environ.get("TWILIO_AUTH_TOKEN")
        or config.twilio_auth_token_encrypted  # plain-text in v1, encrypted column is future-proofing
    )
    from_number = (
        os.environ.get("TWILIO_PHONE_NUMBER") or config.twilio_phone_number
    )
    return sid, token, from_number


def get_twilio_client(config: SmsConfig):
    """Return an authenticated Twilio REST client.

    Imports the Twilio SDK lazily so the app can boot without the package
    installed when SMS is disabled.
    """
    from twilio.rest import Client  # noqa: WPS433 — lazy import on purpose

    sid, token, _ = get_twilio_credentials(config)
    if not sid or not token:
        raise ValueError(
            "Twilio credentials not configured. Set TWILIO_ACCOUNT_SID and "
            "TWILIO_AUTH_TOKEN env vars or populate the sms_config row."
        )
    return Client(sid, token)


# ---------------------------------------------------------------------------
# Template rendering + business hours
# ---------------------------------------------------------------------------
def _split_name(full_name: Optional[str]) -> Tuple[str, str]:
    if not full_name:
        return "", ""
    parts = full_name.strip().split(None, 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first, last


def render_template(template: str, contact: Optional[Contact] = None, **kwargs) -> str:
    """Replace personalization tokens in a template string.

    Supported tokens:
      {first_name}, {last_name}, {full_name}, {company_name}, {rep_name},
      {estimate_url}, {invoice_url}
    Missing values render as empty string (not as the literal token).
    """
    first, last = _split_name(getattr(contact, "name", None) if contact else None)
    tokens = {
        "first_name": first,
        "last_name": last,
        "full_name": (getattr(contact, "name", "") or "") if contact else "",
        "company_name": (getattr(contact, "company", "") or "") if contact else "",
        "rep_name": "",
        "estimate_url": "",
        "invoice_url": "",
    }
    tokens.update({k: ("" if v is None else str(v)) for k, v in kwargs.items()})

    out = template
    for key, value in tokens.items():
        out = out.replace("{" + key + "}", value)
    return out


def is_business_hours(config: SmsConfig, now: Optional[datetime] = None) -> bool:
    """Return True if `now` falls within business hours in the configured timezone.

    Boundaries: start inclusive, end exclusive — 8:00am = yes, 5:59pm = yes,
    6:00pm = no (per Sprint 17 spec).
    """
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(config.business_timezone)
    except Exception:
        tz = timezone.utc

    if now is None:
        now = datetime.now(tz=tz)
    else:
        if now.tzinfo is None:
            now = now.replace(tzinfo=tz)
        else:
            now = now.astimezone(tz)

    t = now.time().replace(microsecond=0)
    start = config.business_hours_start
    end = config.business_hours_end
    return start <= t < end


# ---------------------------------------------------------------------------
# Send / receive
# ---------------------------------------------------------------------------
def _find_contact_by_phone(db: Session, incoming_e164: str) -> Optional[Contact]:
    candidates = db.query(Contact).filter(Contact.phone.isnot(None)).all()
    for c in candidates:
        if match_phone(c.phone, incoming_e164):
            return c
    return None


def _record_message(
    db: Session,
    *,
    contact_id: int,
    direction: str,
    body: str,
    from_number: str,
    to_number: str,
    status: str,
    twilio_sid: Optional[str] = None,
    status_detail: Optional[str] = None,
    triggered_by: Optional[str] = None,
    sent_by: Optional[int] = None,
) -> SmsMessage:
    msg = SmsMessage(
        contact_id=contact_id,
        direction=direction,
        body=body,
        from_number=from_number,
        to_number=to_number,
        status=status,
        twilio_sid=twilio_sid,
        status_detail=status_detail,
        triggered_by=triggered_by,
        sent_by=sent_by,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def send_sms(
    db: Session,
    contact_id: int,
    body: str,
    triggered_by: str = "manual",
    sent_by: Optional[int] = None,
) -> SmsMessage:
    """Send an SMS to a contact. Persists an sms_messages row regardless of
    Twilio outcome (status records success / failure).

    Raises:
        ValueError: if the contact does not exist, has no phone, or has opted
            out of SMS.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise ValueError(f"Contact {contact_id} not found")
    if contact.sms_opt_out:
        raise ValueError(
            f"Contact {contact_id} has opted out of SMS messages"
        )
    if not contact.phone:
        raise ValueError(f"Contact {contact_id} has no phone number on file")

    to_e164 = normalize_to_e164(contact.phone)
    if not to_e164:
        raise ValueError(
            f"Contact {contact_id} phone {contact.phone!r} cannot be parsed as a US number"
        )

    config = ensure_sms_config(db)
    sid, token, from_number = get_twilio_credentials(config)

    if not sms_enabled():
        # Kill switch — record the intent but never call Twilio.
        return _record_message(
            db,
            contact_id=contact.id,
            direction="outbound",
            body=body,
            from_number=from_number or "",
            to_number=to_e164,
            status="failed",
            status_detail="SMS_ENABLED is false; message not sent.",
            triggered_by=triggered_by,
            sent_by=sent_by,
        )
    if not sid or not token or not from_number:
        return _record_message(
            db,
            contact_id=contact.id,
            direction="outbound",
            body=body,
            from_number=from_number or "",
            to_number=to_e164,
            status="failed",
            status_detail="Twilio credentials not configured.",
            triggered_by=triggered_by,
            sent_by=sent_by,
        )

    try:
        client = get_twilio_client(config)
        twilio_msg = client.messages.create(
            to=to_e164,
            from_=from_number,
            body=body,
        )
        return _record_message(
            db,
            contact_id=contact.id,
            direction="outbound",
            body=body,
            from_number=from_number,
            to_number=to_e164,
            status=getattr(twilio_msg, "status", "queued") or "queued",
            twilio_sid=getattr(twilio_msg, "sid", None),
            triggered_by=triggered_by,
            sent_by=sent_by,
        )
    except Exception as exc:  # pragma: no cover — exercised via test mocks
        logger.exception("Twilio send failed for contact %s", contact.id)
        return _record_message(
            db,
            contact_id=contact.id,
            direction="outbound",
            body=body,
            from_number=from_number,
            to_number=to_e164,
            status="failed",
            status_detail=str(exc)[:1000],
            triggered_by=triggered_by,
            sent_by=sent_by,
        )


def receive_sms(
    db: Session,
    from_number: str,
    to_number: str,
    body: str,
    twilio_sid: Optional[str] = None,
) -> SmsMessage:
    """Process an inbound SMS.

    Steps:
      1. Look up the contact by phone (normalized match).
      2. If no contact exists, create a stub contact.
      3. Detect opt-out / opt-in / HELP keywords against sms_config.
      4. Persist an inbound sms_messages row.
    """
    config = ensure_sms_config(db)
    incoming_e164 = normalize_to_e164(from_number) or from_number

    contact = _find_contact_by_phone(db, incoming_e164)
    if not contact:
        display = format_for_display(incoming_e164) or incoming_e164
        contact = Contact(
            name=f"Unknown - {display}",
            phone=display,
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)

    keyword = (body or "").strip().upper()
    opt_out_set = {
        k.strip().upper() for k in (config.opt_out_keywords or "").split(",") if k.strip()
    }
    opt_in_set = {
        k.strip().upper() for k in (config.opt_in_keywords or "").split(",") if k.strip()
    }

    if keyword in opt_out_set:
        contact.sms_opt_out = True
        contact.sms_opt_out_at = datetime.now(tz=timezone.utc)
        db.commit()
    elif keyword in opt_in_set:
        contact.sms_opt_out = False
        contact.sms_opt_out_at = None
        db.commit()
    elif keyword == "HELP":
        # Reply with help_response. send_sms handles its own commit.
        try:
            send_sms(
                db,
                contact.id,
                config.help_response,
                triggered_by="auto_help_response",
            )
        except ValueError:
            # Contact is somehow not sendable — still record the inbound.
            pass

    return _record_message(
        db,
        contact_id=contact.id,
        direction="inbound",
        body=body or "",
        from_number=incoming_e164,
        to_number=normalize_to_e164(to_number) or to_number,
        status="received",
        twilio_sid=twilio_sid,
    )


def auto_respond_new_lead(db: Session, contact_id: int) -> Optional[SmsMessage]:
    """Send an auto-response SMS when a new lead is created.

    No-ops (returns None) when:
      - SMS is disabled (SMS_ENABLED=false)
      - auto_respond_new_lead toggle is off
      - the contact has no phone number
      - the contact has opted out
    """
    if not sms_enabled():
        return None

    config = ensure_sms_config(db)
    if not config.auto_respond_new_lead:
        return None

    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact or not contact.phone or contact.sms_opt_out:
        return None

    if is_business_hours(config):
        template = config.new_lead_template
        triggered = "auto_new_lead"
    else:
        if not config.auto_respond_after_hours:
            return None
        template = config.after_hours_template
        triggered = "auto_new_lead_after_hours"

    body = render_template(template, contact)
    try:
        return send_sms(db, contact.id, body, triggered_by=triggered)
    except ValueError:
        return None


def send_estimate_link(
    db: Session,
    contact_id: int,
    estimate_id: int,
    sent_by: Optional[int] = None,
) -> Optional[SmsMessage]:
    """Send the estimate portal URL to the contact via SMS."""
    from app.models.estimate import Estimate
    from app.models.estimate_token import EstimateToken

    if not sms_enabled():
        return None

    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise ValueError(f"Estimate {estimate_id} not found")

    token_row = (
        db.query(EstimateToken)
        .filter(EstimateToken.estimate_id == estimate_id)
        .order_by(EstimateToken.created_at.desc())
        .first()
    )
    base_url = os.environ.get("PORTAL_BASE_URL", "").rstrip("/")
    if token_row and base_url:
        estimate_url = f"{base_url}/portal/estimate/{token_row.token}"
    elif token_row:
        estimate_url = f"/portal/estimate/{token_row.token}"
    else:
        estimate_url = ""

    config = ensure_sms_config(db)
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    body = render_template(
        config.estimate_sent_template,
        contact,
        estimate_url=estimate_url,
    )
    return send_sms(
        db,
        contact_id,
        body,
        triggered_by="auto_estimate_sent",
        sent_by=sent_by,
    )
