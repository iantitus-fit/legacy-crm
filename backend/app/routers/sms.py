"""Sprint 17b — SMS API endpoints.

Endpoints:
- POST   /api/sms/send                         manual outbound SMS
- POST   /api/sms/send-estimate                send estimate portal link
- GET    /api/contacts/{contact_id}/sms        conversation history (paginated)
- GET    /api/sms/config                       config (admin)
- PUT    /api/sms/config                       update config (admin)

Webhook endpoints live in routers/sms_webhooks.py because they use a
different auth model (Twilio signature instead of JWT).
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contact import Contact
from app.models.sms import SmsConfig, SmsMessage
from app.models.user import User
from app.schemas.sms import (
    SmsConfigResponse,
    SmsConfigUpdate,
    SmsConversationResponse,
    SmsMessageResponse,
    SmsSendEstimateRequest,
    SmsSendRequest,
)
from app.services import sms_service
from app.utils.dependencies import get_current_user, require_admin

logger = logging.getLogger("legacy_crm.sms")

router = APIRouter(tags=["sms"])


def _message_to_response(msg: SmsMessage, db: Session) -> SmsMessageResponse:
    contact = db.query(Contact).filter(Contact.id == msg.contact_id).first()
    contact_name = contact.name if contact else None
    sender_name = None
    if msg.sent_by:
        sender = db.query(User).filter(User.id == msg.sent_by).first()
        sender_name = sender.full_name if sender else None
    return SmsMessageResponse(
        id=msg.id,
        contact_id=msg.contact_id,
        contact_name=contact_name,
        direction=msg.direction,
        body=msg.body,
        from_number=msg.from_number,
        to_number=msg.to_number,
        twilio_sid=msg.twilio_sid,
        status=msg.status,
        status_detail=msg.status_detail,
        triggered_by=msg.triggered_by,
        sent_by=msg.sent_by,
        sent_by_name=sender_name,
        read_at=msg.read_at,
        created_at=msg.created_at,
        updated_at=msg.updated_at,
    )


# ---------------------------------------------------------------------------
# Outbound — manual send
# ---------------------------------------------------------------------------
@router.post("/api/sms/send", response_model=SmsMessageResponse)
def send_sms(
    payload: SmsSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == payload.contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    try:
        msg = sms_service.send_sms(
            db,
            payload.contact_id,
            payload.body,
            triggered_by="manual",
            sent_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _message_to_response(msg, db)


@router.post("/api/sms/send-estimate", response_model=SmsMessageResponse)
def send_estimate_sms(
    payload: SmsSendEstimateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == payload.contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    try:
        msg = sms_service.send_estimate_link(
            db,
            payload.contact_id,
            payload.estimate_id,
            sent_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if msg is None:
        raise HTTPException(
            status_code=400,
            detail="SMS is disabled (SMS_ENABLED=false).",
        )
    return _message_to_response(msg, db)


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------
@router.get(
    "/api/contacts/{contact_id}/sms",
    response_model=SmsConversationResponse,
)
def get_conversation(
    contact_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    query = db.query(SmsMessage).filter(SmsMessage.contact_id == contact_id)
    total = query.count()
    items = (
        query.order_by(SmsMessage.created_at.desc(), SmsMessage.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return SmsConversationResponse(
        items=[_message_to_response(m, db) for m in items],
        total=total,
        page=page,
        per_page=per_page,
    )


# ---------------------------------------------------------------------------
# Config CRUD (admin)
# ---------------------------------------------------------------------------
@router.get("/api/sms/config", response_model=SmsConfigResponse)
def get_config(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = sms_service.ensure_sms_config(db)
    return config


@router.put("/api/sms/config", response_model=SmsConfigResponse)
def update_config(
    payload: SmsConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = sms_service.ensure_sms_config(db)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    db.commit()
    db.refresh(config)
    return config
