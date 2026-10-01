"""Work-order routes.

A work order is a rendered view of an estimate — no new table, just a
PDF renderer plus a public-by-token route so crews/subs can open the
link without logging in.

Auth boundary:
- /api/estimates/{id}/work-order            — auth (download PDF)
- /api/estimates/{id}/work-order/send       — auth (email PDF)
- /api/estimates/{id}/work-order/link       — auth (returns public token + URL)
- /api/work-orders/{token}                  — no auth (public PDF)
"""
import logging
import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.work_order_token import WorkOrderToken
from app.routers.estimates import _load_estimate
from app.services.email_service import send_email
from app.services.work_order_pdf import (
    build_work_order_context,
    render_work_order_pdf,
)
from app.utils.dependencies import get_current_user
from app.utils.portal_links import ensure_not_expired, is_expired, link_expiry

logger = logging.getLogger("legacy_crm")

router = APIRouter(tags=["work-orders"])

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)


class SendWorkOrderRequest(BaseModel):
    recipient_email: EmailStr
    secret: bool = False
    message: Optional[str] = None


def _pdf_response(pdf_bytes: bytes, wo_number: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{wo_number}.pdf"'
        },
    )


def _get_or_create_token(
    db: Session, *, estimate_id: int, is_secret: bool, created_by: Optional[int]
) -> WorkOrderToken:
    existing = (
        db.query(WorkOrderToken)
        .filter(
            WorkOrderToken.estimate_id == estimate_id,
            WorkOrderToken.is_secret == is_secret,
        )
        .first()
    )
    if existing:
        if is_expired(existing.expires_at):
            existing.expires_at = link_expiry()
            db.commit()
            db.refresh(existing)
        return existing
    token = WorkOrderToken(
        estimate_id=estimate_id,
        token=uuid4().hex,
        is_secret=is_secret,
        created_by=created_by,
        expires_at=link_expiry(),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


@router.get("/api/estimates/{estimate_id}/work-order")
def get_work_order_pdf(
    estimate_id: int,
    secret: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _load_estimate(db, estimate_id)  # 404 if missing
    pdf_bytes, wo_number = render_work_order_pdf(db, estimate_id, secret=secret)
    return _pdf_response(pdf_bytes, wo_number)


@router.post("/api/estimates/{estimate_id}/work-order/link")
def create_work_order_link(
    estimate_id: int,
    secret: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = _load_estimate(db, estimate_id)
    # Make sure work_order_number exists so the URL is meaningful when copied
    build_work_order_context(db, estimate, secret=secret)
    token = _get_or_create_token(
        db,
        estimate_id=estimate_id,
        is_secret=secret,
        created_by=current_user.id,
    )
    portal_base = os.environ.get("PORTAL_BASE_URL", "http://localhost:5173")
    return {
        "token": token.token,
        "url": f"{portal_base.rstrip('/')}/api/work-orders/{token.token}",
        "secret": token.is_secret,
    }


@router.post("/api/estimates/{estimate_id}/work-order/send")
def send_work_order_email(
    estimate_id: int,
    data: SendWorkOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = _load_estimate(db, estimate_id)
    pdf_bytes, wo_number = render_work_order_pdf(
        db, estimate_id, secret=data.secret
    )

    context = build_work_order_context(db, estimate, secret=data.secret)
    email_template = _jinja_env.get_template("work_order_email.html")
    email_html = email_template.render(
        wo_number=wo_number,
        secret=data.secret,
        message=data.message,
        job_address=context.get("job_address"),
        company_name="Legacy Roofing & Exteriors",
        company_phone="(615) 555-0100",
    )
    subject = (
        f"Secret Work Order {wo_number}"
        if data.secret
        else f"Work Order {wo_number}"
    )
    filename = f"{wo_number}.pdf"

    try:
        send_email(
            to_email=data.recipient_email,
            subject=subject,
            html_body=email_html,
            attachment_bytes=pdf_bytes,
            attachment_filename=filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Failed to send work order email")
        raise HTTPException(
            status_code=500, detail=f"Failed to send email: {str(e)}"
        )

    return {
        "sent_to": data.recipient_email,
        "wo_number": wo_number,
        "secret": data.secret,
    }


@router.get("/api/work-orders/{token}")
def public_work_order(token: str, db: Session = Depends(get_db)):
    row = (
        db.query(WorkOrderToken).filter(WorkOrderToken.token == token).first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Work order not found")
    ensure_not_expired(row)
    pdf_bytes, wo_number = render_work_order_pdf(
        db, row.estimate_id, secret=row.is_secret
    )
    return _pdf_response(pdf_bytes, wo_number)
