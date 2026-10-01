import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.estimate import Estimate
from app.models.estimate_signature import EstimateSignature
from app.models.estimate_status_history import EstimateStatusHistory
from app.models.estimate_token import EstimateToken
from app.models.job import Job
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.user import User
from app.routers.estimate_export import _build_template_context, _render_estimate_html
from app.routers.estimates import _estimate_to_response, _load_estimate
from app.schemas.customer_portal import ApproveBody, ChangeRequestBody, RejectBody
from app.services.email_service import send_email
from app.services.estimate_approval import OPEN_FOR_RESPONSE, approve_estimate
from app.utils.portal_links import ensure_not_expired

logger = logging.getLogger("legacy_crm")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)

router = APIRouter(prefix="/api/portal", tags=["customer-portal"])


def _get_estimate_from_token(token: str, db: Session) -> Estimate:
    """Look up an estimate by portal token."""
    record = db.query(EstimateToken).filter(EstimateToken.token == token).first()
    if not record:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    ensure_not_expired(record)
    estimate = _load_estimate(db, record.estimate_id)
    return estimate


def _require_open(estimate: Estimate) -> None:
    """Approve, reject and request-changes only work while the estimate awaits an answer."""
    if estimate.status not in OPEN_FOR_RESPONSE:
        raise HTTPException(
            status_code=409,
            detail="This estimate is no longer open for a response.",
        )


def _track_viewed(estimate: Estimate, ip: str, db: Session) -> None:
    """On first access, transition from 'sent' to 'viewed'."""
    if estimate.status == "sent":
        estimate.status = "viewed"
        db.add(EstimateStatusHistory(
            estimate_id=estimate.id,
            status="viewed",
            ip_address=ip,
        ))
        db.commit()
        db.refresh(estimate)


def _send_action_notification(
    token: str, estimate: Estimate, action_type: str,
    customer_name: str, db: Session, notes: str = None,
) -> None:
    """Send email notification to the company when a customer takes an action."""
    try:
        # Find the user who sent this estimate
        token_record = db.query(EstimateToken).filter(
            EstimateToken.token == token
        ).first()
        recipient_email = None
        if token_record and token_record.created_by:
            user = db.query(User).filter(User.id == token_record.created_by).first()
            if user:
                recipient_email = user.email
        if not recipient_email:
            recipient_email = os.environ.get("SMTP_FROM_EMAIL", "") or os.environ.get("SMTP_USER", "")
        if not recipient_email:
            logger.warning("No recipient email for customer action notification")
            return

        portal_base = os.environ.get("PORTAL_BASE_URL", "http://localhost:5173")
        estimate_url = f"{portal_base}/estimates/{estimate.id}"

        template = jinja_env.get_template("customer_action_email.html")
        html_body = template.render(
            action_type=action_type,
            customer_name=customer_name,
            estimate_name=estimate.name or "Estimate",
            timestamp=datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            notes=notes,
            estimate_url=estimate_url,
            company_name="Legacy Roofing & Exteriors",
            company_phone="(615) 555-0100",
            company_email="info@legacy-roofing.example",
        )

        subject = f"Estimate {action_type}: {estimate.name or 'Estimate'}"
        send_email(to_email=recipient_email, subject=subject, html_body=html_body)
    except Exception:
        logger.exception("Failed to send customer action notification email")


@router.get("/{token}")
def get_portal_estimate(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    estimate = _get_estimate_from_token(token, db)
    ip = request.client.host if request.client else None
    _track_viewed(estimate, ip, db)
    data = _estimate_to_response(estimate)
    return data


@router.get("/{token}/preview")
def portal_preview(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    estimate = _get_estimate_from_token(token, db)
    ip = request.client.host if request.client else None
    _track_viewed(estimate, ip, db)
    html = _render_estimate_html(estimate.id, db)
    return HTMLResponse(content=html)


@router.get("/{token}/pdf")
def portal_pdf(
    token: str,
    db: Session = Depends(get_db),
):
    from weasyprint import HTML

    estimate = _get_estimate_from_token(token, db)
    html = _render_estimate_html(estimate.id, db)
    safe_name = (estimate.name or "Estimate").replace(" ", "_").encode("ascii", "ignore").decode()
    filename = f"Estimate_{safe_name}_{estimate.id}.pdf"
    pdf_bytes = HTML(string=html).write_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{token}/request-changes")
def portal_request_changes(
    token: str,
    body: ChangeRequestBody,
    request: Request,
    db: Session = Depends(get_db),
):
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=422, detail="Message is required")
    estimate = _get_estimate_from_token(token, db)
    ip = request.client.host if request.client else None
    _require_open(estimate)
    estimate.status = "changes_requested"
    db.add(EstimateStatusHistory(
        estimate_id=estimate.id,
        status="changes_requested",
        ip_address=ip,
        notes=body.message,
    ))
    db.commit()
    _send_action_notification(
        token, estimate, "requested changes", "A customer", db, notes=body.message,
    )
    return {"success": True, "message": "Change request submitted"}


@router.post("/{token}/reject")
def portal_reject(
    token: str,
    body: RejectBody,
    request: Request,
    db: Session = Depends(get_db),
):
    estimate = _get_estimate_from_token(token, db)
    ip = request.client.host if request.client else None
    _require_open(estimate)
    estimate.status = "rejected"
    db.add(EstimateStatusHistory(
        estimate_id=estimate.id,
        status="rejected",
        changed_by_name=body.name,
        ip_address=ip,
        notes=body.reason,
    ))
    db.commit()
    _send_action_notification(
        token, estimate, "rejected", body.name or "A customer", db, notes=body.reason,
    )
    return {"success": True, "message": "Estimate rejected"}


@router.post("/{token}/approve")
def portal_approve(
    token: str,
    body: ApproveBody,
    request: Request,
    db: Session = Depends(get_db),
):
    if not body.signer_name or not body.signer_name.strip():
        raise HTTPException(status_code=422, detail="Signer name is required")
    if not body.signature_data or not body.signature_data.strip():
        raise HTTPException(status_code=422, detail="Signature data is required")
    if not body.terms_accepted:
        raise HTTPException(status_code=422, detail="Terms must be accepted")

    estimate = _get_estimate_from_token(token, db)
    ip = request.client.host if request.client else None

    _require_open(estimate)
    db.add(EstimateSignature(
        estimate_id=estimate.id,
        signer_name=body.signer_name,
        signature_data=body.signature_data,
        ip_address=ip,
        terms_accepted=body.terms_accepted,
    ))
    # Same path as approve-internal: status, approved_at/by, history, and
    # placement on the Jobs board (estimate and job row).
    approve_estimate(db, estimate, approved_by=body.signer_name.strip()[:100], ip_address=ip)

    db.commit()
    _send_action_notification(
        token, estimate, "approved", body.signer_name, db,
    )

    # Sprint 16b — fire estimate_approved (crew briefing draft)
    contact_id = None
    try:
        if estimate.job and estimate.job.contact:
            contact_id = estimate.job.contact_id
    except Exception:
        contact_id = None
    from app.services.ai_events import safe_dispatch

    safe_dispatch(
        db=db,
        event_type="estimate_approved",
        contact_id=contact_id,
        estimate_id=estimate.id,
    )

    return {"success": True, "message": "Estimate approved"}
