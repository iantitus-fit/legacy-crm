"""Sprint 17b — Twilio webhook endpoints.

These endpoints cannot use JWT auth because Twilio cannot send bearer
tokens. Instead, we validate the `X-Twilio-Signature` header using the
twilio.request_validator.RequestValidator with our Twilio auth token.

Endpoints:
- POST /api/webhooks/twilio/inbound   inbound SMS from a customer
- POST /api/webhooks/twilio/status    Twilio status callback for outbound

Both expect application/x-www-form-urlencoded request bodies (Twilio's
default for webhook callbacks), not JSON.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contact import Contact
from app.models.sms import SmsMessage
from app.services import automation_service, sms_service

logger = logging.getLogger("legacy_crm.sms")

router = APIRouter(prefix="/api/webhooks/twilio", tags=["twilio-webhooks"])


def _resolve_auth_token(db: Session) -> str:
    config = sms_service.ensure_sms_config(db)
    sid, token, _ = sms_service.get_twilio_credentials(config)
    return token or ""


async def _validate_twilio_signature(
    request: Request, form_data: Dict[str, str], auth_token: str
) -> bool:
    """Validate the X-Twilio-Signature header against the request.

    Returns False (does not raise) so the caller can return 403.
    In development, allow bypass when TWILIO_WEBHOOK_SKIP_SIGNATURE=true
    so ngrok-fronted requests with rewritten URLs work locally.
    """
    if (
        os.environ.get("TWILIO_WEBHOOK_SKIP_SIGNATURE", "false").strip().lower()
        in ("1", "true", "yes")
    ):
        return True
    if not auth_token:
        return False
    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        logger.error("twilio package not installed; cannot validate signature")
        return False

    validator = RequestValidator(auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    return validator.validate(url, form_data, signature)


@router.post("/inbound")
async def twilio_inbound(request: Request, db: Session = Depends(get_db)):
    """Receive an inbound SMS. Returns empty TwiML <Response/> — replies are
    sent through our own send_sms flow so they're tracked in our DB."""
    form = await request.form()
    form_data = {k: str(v) for k, v in form.items()}

    auth_token = _resolve_auth_token(db)
    if not await _validate_twilio_signature(request, form_data, auth_token):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    from_number = form_data.get("From", "")
    to_number = form_data.get("To", "")
    body = form_data.get("Body", "")
    twilio_sid = form_data.get("MessageSid")

    if not from_number:
        raise HTTPException(status_code=400, detail="Missing From")

    try:
        message = sms_service.receive_sms(
            db,
            from_number=from_number,
            to_number=to_number,
            body=body,
            twilio_sid=twilio_sid,
        )
        # Sprint 19b — every inbound message counts as a reply; stop any
        # active enrollments whose current step opts in to stop_on_reply.
        # If the inbound was a STOP keyword, receive_sms already flipped
        # sms_opt_out — also stop any SMS-bearing sequences.
        if message and message.contact_id:
            try:
                automation_service.check_reply_stop(db, message.contact_id)
                contact_row = (
                    db.query(Contact)
                    .filter(Contact.id == message.contact_id)
                    .first()
                )
                if contact_row and contact_row.sms_opt_out:
                    automation_service.check_optout_stop(
                        db, message.contact_id
                    )
            except Exception:  # pragma: no cover
                logger.exception(
                    "automation stop check failed for contact %s",
                    message.contact_id,
                )
    except Exception:  # pragma: no cover
        logger.exception("Failed to process inbound SMS")
        # Still return 200 so Twilio doesn't retry indefinitely.

    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
        media_type="application/xml",
    )


@router.post("/status")
async def twilio_status(request: Request, db: Session = Depends(get_db)):
    """Update an outbound message's status from a Twilio status callback."""
    form = await request.form()
    form_data = {k: str(v) for k, v in form.items()}

    auth_token = _resolve_auth_token(db)
    if not await _validate_twilio_signature(request, form_data, auth_token):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    message_sid = form_data.get("MessageSid")
    new_status = form_data.get("MessageStatus") or form_data.get("SmsStatus")
    error_message = form_data.get("ErrorMessage") or form_data.get("ErrorCode")

    if not message_sid or not new_status:
        raise HTTPException(status_code=400, detail="Missing MessageSid or status")

    msg = (
        db.query(SmsMessage)
        .filter(SmsMessage.twilio_sid == message_sid)
        .first()
    )
    if msg:
        msg.status = new_status
        if error_message:
            msg.status_detail = str(error_message)[:1000]
        msg.updated_at = datetime.now(tz=timezone.utc)
        db.commit()

    return Response(status_code=200)
