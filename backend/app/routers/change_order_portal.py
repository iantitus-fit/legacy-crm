import base64
import logging
import os
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.change_order import ChangeOrder
from app.models.change_order_signature import ChangeOrderSignature
from app.models.change_order_token import ChangeOrderToken
from app.models.estimate import Estimate
from app.models.job import Job
from app.models.contact import Contact
from app.models.user import User
from app.schemas.change_order_portal import COApproveBody, COChangeRequestBody, CORejectBody
from app.services.email_service import send_email
from app.services.estimate_approval import OPEN_FOR_RESPONSE
from app.utils.portal_links import ensure_not_expired

logger = logging.getLogger("legacy_crm")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)

router = APIRouter(prefix="/api/portal/co", tags=["change-order-portal"])


def _require_open_co(co: ChangeOrder) -> None:
    """A change order can be answered once; a resend reopens it."""
    if co.status not in OPEN_FOR_RESPONSE:
        raise HTTPException(
            status_code=409,
            detail="This change order is no longer open for a response.",
        )


def _get_co_from_token(token: str, db: Session) -> ChangeOrder:
    """Look up a change order by portal token."""
    record = db.query(ChangeOrderToken).filter(ChangeOrderToken.token == token).first()
    if not record:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    ensure_not_expired(record)
    co = (
        db.query(ChangeOrder)
        .options(joinedload(ChangeOrder.items))
        .filter(ChangeOrder.id == record.change_order_id)
        .first()
    )
    if not co:
        raise HTTPException(status_code=404, detail="Change order not found")
    return co


def _build_co_template_context(co: ChangeOrder, db: Session) -> dict:
    """Build the Jinja2 template context for CO PDF rendering."""
    estimate = db.query(Estimate).filter(Estimate.id == co.estimate_id).first()
    contact_name = None
    job_address = None
    if estimate and estimate.job_id:
        job = db.query(Job).filter(Job.id == estimate.job_id).first()
        if job:
            job_address = job.property_address
            if job.contact_id:
                contact = db.query(Contact).filter(Contact.id == job.contact_id).first()
                if contact:
                    contact_name = contact.name

    # Load logo
    logo_path = os.path.join(STATIC_DIR, "logo.png")
    logo_data_uri = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_bytes = f.read()
        logo_b64 = base64.b64encode(logo_bytes).decode("utf-8")
        logo_data_uri = f"data:image/png;base64,{logo_b64}"

    items = sorted(co.items, key=lambda i: i.sort_order or 0)

    tax_rate = Decimal(str(estimate.tax_rate or "0.07")) if estimate else Decimal("0.07")
    tax_rate_pct = (tax_rate * Decimal("100")).quantize(Decimal("0.01"))

    # Check for signature
    signature = (
        db.query(ChangeOrderSignature)
        .filter(ChangeOrderSignature.change_order_id == co.id)
        .first()
    )

    return {
        "company_name": "Legacy Roofing & Exteriors",
        "company_address": "Franklin, TN",
        "company_phone": "(615) 555-0100",
        "company_email": "info@legacy-roofing.example",
        "logo_data_uri": logo_data_uri,
        "co_number": co.co_number,
        "co_name": co.name,
        "created_at": co.created_at,
        "estimate_name": estimate.name if estimate else "",
        "contact_name": contact_name,
        "job_address": job_address,
        "items": [
            {
                "description": item.description,
                "qty": item.qty,
                "unit_price": item.unit_price,
                "line_total": item.line_total,
                "body": item.body,
            }
            for item in items
        ],
        "subtotal": co.subtotal or Decimal("0"),
        "tax_rate": tax_rate,
        "tax_rate_pct": tax_rate_pct,
        "tax_amount": co.tax or Decimal("0"),
        "total": co.total or Decimal("0"),
        "signature_data": signature.signature_data if signature else None,
        "signer_name": signature.signer_name if signature else None,
        "signed_at": signature.signed_at if signature else None,
    }


def _render_co_html(co: ChangeOrder, db: Session) -> str:
    """Build context and render the CO PDF template."""
    context = _build_co_template_context(co, db)
    template = jinja_env.get_template("change_order_pdf.html")
    return template.render(**context)


def _send_co_action_notification(
    token: str, co: ChangeOrder, action_type: str,
    customer_name: str, db: Session, notes: str = None,
) -> None:
    """Send email notification to the company when a customer takes action on a CO."""
    try:
        token_record = db.query(ChangeOrderToken).filter(
            ChangeOrderToken.token == token
        ).first()
        recipient_email = None
        if token_record and token_record.created_by:
            user = db.query(User).filter(User.id == token_record.created_by).first()
            if user:
                recipient_email = user.email
        if not recipient_email:
            recipient_email = os.environ.get("SMTP_FROM_EMAIL", "") or os.environ.get("SMTP_USER", "")
        if not recipient_email:
            logger.warning("No recipient email for CO action notification")
            return

        estimate = db.query(Estimate).filter(Estimate.id == co.estimate_id).first()
        portal_base = os.environ.get("PORTAL_BASE_URL", "http://localhost:5173")
        estimate_url = f"{portal_base}/estimates/{estimate.id}" if estimate else ""

        template = jinja_env.get_template("change_order_action_email.html")
        html_body = template.render(
            action_type=action_type,
            customer_name=customer_name,
            co_name=co.name,
            co_number=co.co_number,
            estimate_name=estimate.name if estimate else "",
            timestamp=datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            notes=notes,
            estimate_url=estimate_url,
            company_name="Legacy Roofing & Exteriors",
            company_phone="(615) 555-0100",
            company_email="info@legacy-roofing.example",
        )

        subject = f"Change Order {action_type}: #{co.co_number} - {co.name or 'Change Order'}"
        send_email(to_email=recipient_email, subject=subject, html_body=html_body)
    except Exception:
        logger.exception("Failed to send CO action notification email")


@router.get("/{token}")
def get_portal_co(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    co = _get_co_from_token(token, db)

    # Track viewed
    if co.status == "sent":
        co.status = "viewed"
        db.commit()
        db.refresh(co)

    # Build response with parent estimate info
    estimate = db.query(Estimate).filter(Estimate.id == co.estimate_id).first()
    contact_name = None
    contact_email = None
    job_address = None
    if estimate and estimate.job_id:
        job = db.query(Job).filter(Job.id == estimate.job_id).first()
        if job:
            job_address = job.property_address
            if job.contact_id:
                contact = db.query(Contact).filter(Contact.id == job.contact_id).first()
                if contact:
                    contact_name = contact.name
                    contact_email = contact.email

    items = sorted(co.items, key=lambda i: i.sort_order or 0)
    return {
        "id": co.id,
        "estimate_id": co.estimate_id,
        "co_number": co.co_number,
        "name": co.name,
        "status": co.status,
        "subtotal": co.subtotal,
        "tax": co.tax,
        "total": co.total,
        "created_at": co.created_at,
        "estimate_name": estimate.name if estimate else None,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "job_address": job_address,
        "items": [
            {
                "id": item.id,
                "description": item.description,
                "qty": item.qty,
                "unit_price": item.unit_price,
                "line_total": item.line_total,
                "body": item.body,
                "notes": item.notes,
                "sort_order": item.sort_order,
            }
            for item in items
        ],
    }


@router.get("/{token}/preview")
def portal_co_preview(
    token: str,
    db: Session = Depends(get_db),
):
    co = _get_co_from_token(token, db)
    html = _render_co_html(co, db)
    return HTMLResponse(content=html)


@router.get("/{token}/pdf")
def portal_co_pdf(
    token: str,
    db: Session = Depends(get_db),
):
    from weasyprint import HTML

    co = _get_co_from_token(token, db)
    html = _render_co_html(co, db)
    safe_name = (co.name or "ChangeOrder").replace(" ", "_").encode("ascii", "ignore").decode()
    filename = f"ChangeOrder_{co.co_number}_{safe_name}.pdf"
    pdf_bytes = HTML(string=html).write_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{token}/approve")
def portal_co_approve(
    token: str,
    body: COApproveBody,
    request: Request,
    db: Session = Depends(get_db),
):
    if not body.signer_name or not body.signer_name.strip():
        raise HTTPException(status_code=422, detail="Signer name is required")
    if not body.signature_data or not body.signature_data.strip():
        raise HTTPException(status_code=422, detail="Signature data is required")
    if not body.terms_accepted:
        raise HTTPException(status_code=422, detail="Terms must be accepted")

    co = _get_co_from_token(token, db)
    ip = request.client.host if request.client else None

    _require_open_co(co)
    co.status = "approved"
    db.add(ChangeOrderSignature(
        change_order_id=co.id,
        signer_name=body.signer_name,
        signature_data=body.signature_data,
        ip_address=ip,
        terms_accepted=body.terms_accepted,
    ))
    db.commit()

    _send_co_action_notification(token, co, "approved", body.signer_name, db)
    return {"success": True, "message": "Change order approved"}


@router.post("/{token}/reject")
def portal_co_reject(
    token: str,
    body: CORejectBody,
    request: Request,
    db: Session = Depends(get_db),
):
    co = _get_co_from_token(token, db)
    _require_open_co(co)
    co.status = "rejected"
    db.commit()

    _send_co_action_notification(
        token, co, "rejected", body.name or "A customer", db, notes=body.reason,
    )
    return {"success": True, "message": "Change order rejected"}


@router.post("/{token}/request-changes")
def portal_co_request_changes(
    token: str,
    body: COChangeRequestBody,
    request: Request,
    db: Session = Depends(get_db),
):
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=422, detail="Message is required")
    co = _get_co_from_token(token, db)
    _require_open_co(co)
    co.status = "changes_requested"
    db.commit()

    _send_co_action_notification(
        token, co, "requested changes", "A customer", db, notes=body.message,
    )
    return {"success": True, "message": "Change request submitted"}
