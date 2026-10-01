"""Public booking form endpoint.

POST /api/public/book — no auth. Creates a Contact (or matches an
existing one by phone/email) and a Lead row in the first Leads-pipeline
stage. Fires the same automation/SMS/notification triggers as a
contact created through the authenticated UI, then plays a few
extras: honeypot, simple IP rate limit, and a company-side
notification email to SMTP_FROM_EMAIL.

The spec asked for an "Estimate in Leads pipeline" — but per the
codebase a lead is `Contact + Lead row`. Estimates are proposals
created later in the workflow, so the canonical path here is the same
one POST /api/leads uses.
"""
import logging
import os
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.services.email_service import send_email

logger = logging.getLogger("legacy_crm.booking")

router = APIRouter(prefix="/api/public", tags=["booking"])

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "templates"
)
_jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)


# --- Rate limiting ---------------------------------------------------------
# Simple in-memory IP counter. 5 submissions/hour/IP. Multi-process deploys
# would need Redis or similar, but B1 is a single container so this is fine.
RATE_LIMIT_WINDOW_SECONDS = 3600
RATE_LIMIT_MAX = 5
_rate_lock = Lock()
_rate_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> bool:
    """Return True if request should be allowed."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_lock:
        bucket = _rate_buckets[ip]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_MAX:
            return False
        bucket.append(now)
        return True


def _reset_rate_limits_for_tests() -> None:
    """Test helper — clear all buckets between tests."""
    with _rate_lock:
        _rate_buckets.clear()


# --- Schemas ---------------------------------------------------------------

ALLOWED_SERVICES = {
    "Roofing",
    "Gutters",
    "Siding",
    "Windows",
    "Painting",
    "Other",
}


class BookingRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=7, max_length=30)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=20)
    zip: Optional[str] = Field(None, max_length=20)
    service_type: Optional[str] = Field(None, max_length=50)
    message: Optional[str] = None
    lead_source: Optional[str] = Field(None, max_length=80)
    # Hidden honeypot — real users never fill this.
    company_website: Optional[str] = None

    @validator("service_type")
    def _validate_service_type(cls, v):
        if v in (None, ""):
            return None
        if v not in ALLOWED_SERVICES:
            raise ValueError(f"service_type must be one of {sorted(ALLOWED_SERVICES)}")
        return v


# --- Background tasks ------------------------------------------------------


def _auto_respond_new_lead_task(contact_id: int) -> None:
    from app.services.sms_service import auto_respond_new_lead

    db = SessionLocal()
    try:
        auto_respond_new_lead(db, contact_id)
    except Exception:  # pragma: no cover
        logger.exception("auto_respond_new_lead failed for contact %s", contact_id)
    finally:
        db.close()


def _on_contact_created_task(contact_id: int) -> None:
    from app.services.automation_service import on_contact_created

    db = SessionLocal()
    try:
        on_contact_created(db, contact_id)
    except Exception:  # pragma: no cover
        logger.exception("on_contact_created failed for contact %s", contact_id)
    finally:
        db.close()


def _send_company_notification_task(contact_id: int, payload: dict) -> None:
    db = SessionLocal()
    try:
        recipient = (
            os.environ.get("SMTP_FROM_EMAIL")
            or os.environ.get("SMTP_USER")
        )
        if not recipient:
            logger.warning(
                "Skipping new-lead notification: no SMTP_FROM_EMAIL/SMTP_USER"
            )
            return
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            return
        template = _jinja_env.get_template("new_lead_notification.html")
        html = template.render(
            contact=contact,
            payload=payload,
            source=payload.get("lead_source") or "Website",
        )
        subject = (
            f"New lead: {contact.name}"
            + (f" — {payload['service_type']}" if payload.get("service_type") else "")
        )
        send_email(to_email=recipient, subject=subject, html_body=html)
    except Exception:  # pragma: no cover
        logger.exception(
            "Company notification email failed for contact %s", contact_id
        )
    finally:
        db.close()


# --- Helpers ---------------------------------------------------------------


def _find_existing_contact(
    db: Session, *, phone: str, email: Optional[str]
) -> Optional[Contact]:
    """Match a returning lead by phone OR email so we don't create dupes."""
    filters = [Contact.phone == phone]
    if email:
        filters.append(Contact.email == email)
    return db.query(Contact).filter(or_(*filters)).first()


def _resolve_leads_stage(db: Session) -> tuple[Optional[int], Optional[int]]:
    """Return (leads_pipeline_id, first_stage_id) — either may be None
    if the pipeline isn't seeded (e.g. a barebones test DB)."""
    pipeline = db.query(Pipeline).filter(Pipeline.slug == "leads").first()
    if not pipeline:
        return None, None
    stage = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline.id)
        .order_by(PipelineStage.sort_order)
        .first()
    )
    return pipeline.id, (stage.id if stage else None)


# --- Endpoint --------------------------------------------------------------


@router.post("/book", status_code=201)
def submit_booking(
    payload: BookingRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    # Honeypot: silently accept so bots can't tell they were caught.
    if payload.company_website:
        logger.info("Honeypot hit from %s", _client_ip(request))
        return {
            "success": True,
            "message": "Thanks! We'll be in touch within 24 hours.",
        }

    ip = _client_ip(request)
    if not _check_rate_limit(ip):
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many submissions from your network. "
                "Please try again in an hour or call us directly."
            ),
        )

    leads_pipeline_id, leads_stage_id = _resolve_leads_stage(db)
    full_name = f"{payload.first_name.strip()} {payload.last_name.strip()}".strip()

    contact = _find_existing_contact(db, phone=payload.phone, email=payload.email)
    if contact:
        # Returning lead — refresh fields the user just gave us, but don't
        # clobber non-empty existing values.
        if not contact.email and payload.email:
            contact.email = payload.email
        if not contact.address and payload.address:
            contact.address = payload.address
        if not contact.city and payload.city:
            contact.city = payload.city
        if not contact.zip and payload.zip:
            contact.zip = payload.zip
        if leads_pipeline_id and not contact.pipeline_id:
            contact.pipeline_id = leads_pipeline_id
            contact.stage_id = leads_stage_id
        db.commit()
        db.refresh(contact)
        is_new_contact = False
    else:
        contact = Contact(
            name=full_name,
            phone=payload.phone,
            email=payload.email,
            address=payload.address,
            city=payload.city,
            state=payload.state or "IN",
            zip=payload.zip,
            lead_source=payload.lead_source or "Website",
            pipeline_id=leads_pipeline_id,
            stage_id=leads_stage_id,
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        is_new_contact = True

    # Always create a Lead row so the new submission lands on the board even
    # for returning callers (a second inquiry is its own lead).
    description_parts = []
    if payload.service_type:
        description_parts.append(f"Service: {payload.service_type}")
    if payload.message:
        description_parts.append(payload.message.strip())
    description = "\n\n".join(description_parts) or None

    lead = Lead(
        contact_id=contact.id,
        stage_id=leads_stage_id,
        source=payload.lead_source or "Website",
        description=description,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    # Fire-and-forget triggers
    if is_new_contact:
        background_tasks.add_task(_on_contact_created_task, contact.id)
    background_tasks.add_task(_auto_respond_new_lead_task, contact.id)
    background_tasks.add_task(
        _send_company_notification_task,
        contact.id,
        payload.model_dump(),
    )

    return {
        "success": True,
        "message": "Thanks! We'll be in touch within 24 hours.",
        "contact_id": contact.id,
        "lead_id": lead.id,
    }
