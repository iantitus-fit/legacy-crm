import logging
import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.estimate_status_history import EstimateStatusHistory
from app.models.estimate_token import EstimateToken
from app.models.user import User
from app.routers.estimate_export import _render_estimate_html
from app.routers.estimates import _load_estimate, _estimate_to_response
from app.services.email_service import send_email
from app.utils.dependencies import get_current_user
from app.utils.portal_links import link_expiry

logger = logging.getLogger("legacy_crm")

router = APIRouter(prefix="/api/estimates", tags=["estimate-email"])

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)


class SendEstimateRequest(BaseModel):
    to_email: str
    subject: Optional[str] = None
    message: Optional[str] = None


def _send_estimate_sms_task(
    contact_id: int, estimate_id: int, user_id: int
) -> None:
    """Background task — opens its own DB session. Errors are logged, never raised."""
    from app.database import SessionLocal
    from app.services.sms_service import send_estimate_link

    db = SessionLocal()
    try:
        send_estimate_link(db, contact_id, estimate_id, sent_by=user_id)
    except Exception:  # pragma: no cover
        logger.exception(
            "send_estimate_link failed for contact %s / estimate %s",
            contact_id,
            estimate_id,
        )
    finally:
        db.close()


def _on_estimate_sent_task(contact_id: int, estimate_id: int) -> None:
    """Sprint 19b — enroll contact in any estimate_sent automations."""
    from app.database import SessionLocal
    from app.services.automation_service import on_estimate_sent

    db = SessionLocal()
    try:
        on_estimate_sent(db, contact_id, estimate_id)
    except Exception:  # pragma: no cover
        logger.exception(
            "on_estimate_sent failed for contact %s / estimate %s",
            contact_id,
            estimate_id,
        )
    finally:
        db.close()


@router.post("/{estimate_id}/send")
def send_estimate_email(
    estimate_id: int,
    data: SendEstimateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = _load_estimate(db, estimate_id)
    estimate_data = _estimate_to_response(estimate)

    contact_name = estimate_data.get("contact_name")
    estimate_name = estimate_data.get("name", "Estimate")

    subject = data.subject or "Estimate from Legacy Roofing & Exteriors"
    message = data.message or (
        f"Please find attached your estimate from Legacy Roofing & Exteriors."
    )

    # Create portal token and build URL
    token_value = uuid4().hex
    portal_base = os.environ.get("PORTAL_BASE_URL", "http://localhost:5173")
    portal_url = f"{portal_base}/portal/{token_value}"

    # Render email body
    email_template = jinja_env.get_template("estimate_email.html")
    email_html = email_template.render(
        contact_name=contact_name,
        estimate_name=estimate_name,
        message=message,
        portal_url=portal_url,
        company_name="Legacy Roofing & Exteriors",
        company_phone="(615) 555-0100",
        company_email="info@legacy-roofing.example",
    )

    # Generate PDF
    from weasyprint import HTML

    pdf_html = _render_estimate_html(estimate_id, db)
    safe_name = (estimate.name or "Estimate").replace(" ", "_").encode("ascii", "ignore").decode()
    filename = f"Estimate_{safe_name}_{estimate_id}.pdf"
    pdf_bytes = HTML(string=pdf_html).write_pdf()

    # Send
    try:
        send_email(
            to_email=data.to_email,
            subject=subject,
            html_body=email_html,
            attachment_bytes=pdf_bytes,
            attachment_filename=filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Failed to send estimate email")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    # Create token and update status
    db.add(EstimateToken(
        estimate_id=estimate_id,
        token=token_value,
        created_by=current_user.id,
        expires_at=link_expiry(),
    ))
    estimate.status = "sent"
    db.add(EstimateStatusHistory(
        estimate_id=estimate_id,
        status="sent",
        changed_by_name=current_user.full_name,
    ))
    db.commit()

    # Sprint 17b — fire SMS link in background if the contact has a phone
    # and isn't opted out. send_estimate_link itself respects SMS_ENABLED.
    contact_id_val = estimate_data.get("contact_id")
    contact_phone_val = estimate_data.get("contact_phone")
    if contact_id_val and contact_phone_val:
        from app.models.contact import Contact

        contact_row = (
            db.query(Contact).filter(Contact.id == contact_id_val).first()
        )
        if contact_row and not contact_row.sms_opt_out:
            background_tasks.add_task(
                _send_estimate_sms_task,
                contact_id_val,
                estimate_id,
                current_user.id,
            )

    # Sprint 19b — enroll in any estimate_sent automation sequences
    if contact_id_val:
        background_tasks.add_task(
            _on_estimate_sent_task, contact_id_val, estimate_id
        )

    return {"success": True, "message": f"Estimate sent to {data.to_email}"}
