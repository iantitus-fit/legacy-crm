"""Work order PDF rendering.

A work order is the same estimate shown to crews/subs — line items
and scope, no pricing. The "secret" variant additionally redacts the
customer's name/phone/email so untrusted subcontractors can't see who
the homeowner is.
"""
import base64
import os
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document import Document
from app.models.estimate import Estimate
from app.models.note import Note
from app.routers.estimates import _estimate_to_response, _load_estimate

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

_jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)

# Crew + company notes are internal-facing. Client notes go on the estimate PDF
# instead — surfacing them on the work order would defeat the secret variant.
_WO_NOTE_TYPES = ("crew", "company")


def _logo_data_uri() -> str:
    logo_path = os.path.join(STATIC_DIR, "logo.png")
    if not os.path.exists(logo_path):
        return ""
    with open(logo_path, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"


def _photo_data_uri(doc: Document) -> Optional[str]:
    """Inline a stored photo as a base64 data URI for WeasyPrint."""
    path = Path(settings.upload_dir) / doc.filename
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
    except OSError:
        return None
    return f"data:{doc.content_type};base64,{b64}"


def _ensure_work_order_number(db: Session, estimate: Estimate) -> str:
    if estimate.work_order_number:
        return estimate.work_order_number
    estimate.work_order_number = f"WO-{estimate.id}"
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    return estimate.work_order_number


def _gather_wo_photos(db: Session, estimate_id: int) -> List[dict]:
    photos = (
        db.query(Document)
        .filter(
            Document.estimate_id == estimate_id,
            Document.is_photo.is_(True),
            Document.show_in_work_order.is_(True),
        )
        .order_by(Document.created_at.asc())
        .all()
    )
    out: List[dict] = []
    for p in photos:
        uri = _photo_data_uri(p)
        if not uri:
            continue
        out.append(
            {
                "data_uri": uri,
                "caption": p.description or p.original_filename,
            }
        )
    return out


def _gather_crew_notes(db: Session, estimate_id: int) -> List[Note]:
    return (
        db.query(Note)
        .filter(
            Note.entity_type == "estimate",
            Note.entity_id == estimate_id,
            Note.note_type.in_(_WO_NOTE_TYPES),
        )
        .order_by(Note.created_at.asc())
        .all()
    )


def build_work_order_context(
    db: Session, estimate: Estimate, *, secret: bool
) -> dict:
    """Build the Jinja2 context. Stamps work_order_number on first call."""
    wo_number = _ensure_work_order_number(db, estimate)
    estimate_data = _estimate_to_response(estimate, db)

    # Customer info is redacted entirely for the secret variant.
    customer: Optional[dict] = None
    if not secret:
        customer = {
            "name": estimate_data.get("contact_name"),
            "phone": estimate_data.get("contact_phone"),
            "email": estimate_data.get("contact_email"),
            "company": estimate_data.get("contact_company"),
            "address": estimate_data.get("contact_address"),
        }

    job_address = (
        estimate_data.get("job_address")
        or estimate.location_address
        or (estimate_data.get("contact_address") if not secret else None)
    )

    # Sections/items use the same shape as the estimate template
    sections = []
    for s in estimate_data.get("sections", []):
        sections.append(
            {
                "name": s.get("name", ""),
                "description": s.get("description"),
                "line_items": [
                    {
                        "description": getattr(li, "description", None)
                        or (li.get("description") if isinstance(li, dict) else None),
                        "qty": getattr(li, "qty", None)
                        or (li.get("qty") if isinstance(li, dict) else None),
                        "body": getattr(li, "body", None)
                        or (li.get("body") if isinstance(li, dict) else None),
                    }
                    for li in s.get("line_items", [])
                ],
            }
        )

    section_ids = {s["id"] for s in estimate_data.get("sections", [])}
    unsectioned_items = []
    for li in estimate_data.get("line_items", []):
        sid = getattr(li, "section_id", None) if not isinstance(li, dict) else li.get("section_id")
        if sid and sid in section_ids:
            continue
        unsectioned_items.append(
            {
                "description": getattr(li, "description", None)
                or (li.get("description") if isinstance(li, dict) else None),
                "qty": getattr(li, "qty", None)
                or (li.get("qty") if isinstance(li, dict) else None),
                "body": getattr(li, "body", None)
                or (li.get("body") if isinstance(li, dict) else None),
            }
        )

    return {
        "wo_number": wo_number,
        "secret": secret,
        "estimate_id": estimate.id,
        "estimate_name": estimate_data.get("name") or "",
        "created_at": estimate_data.get("created_at"),
        "scheduled_start": estimate_data.get("scheduled_start"),
        "scheduled_end": estimate_data.get("scheduled_end"),
        "crew_name": estimate_data.get("crew_name"),
        "scope_of_work": estimate_data.get("scope_of_work"),
        "company_name": "Legacy Roofing & Exteriors",
        "company_address": "Franklin, TN",
        "company_phone": "(615) 555-0100",
        "company_email": "info@legacy-roofing.example",
        "logo_data_uri": _logo_data_uri(),
        "customer": customer,
        "job_address": job_address,
        "sections": sections,
        "unsectioned_items": unsectioned_items,
        "photos": _gather_wo_photos(db, estimate.id),
        "crew_notes": _gather_crew_notes(db, estimate.id),
    }


def render_work_order_html(
    db: Session, estimate_id: int, *, secret: bool
) -> str:
    estimate = _load_estimate(db, estimate_id)
    context = build_work_order_context(db, estimate, secret=secret)
    template = _jinja_env.get_template("work_order_pdf.html")
    return template.render(**context)


def render_work_order_pdf(
    db: Session, estimate_id: int, *, secret: bool
) -> tuple[bytes, str]:
    """Return (pdf_bytes, wo_number). Stamps the number on first call."""
    from weasyprint import HTML

    estimate = _load_estimate(db, estimate_id)
    context = build_work_order_context(db, estimate, secret=secret)
    template = _jinja_env.get_template("work_order_pdf.html")
    html = template.render(**context)
    pdf_bytes = HTML(string=html).write_pdf()
    return pdf_bytes, context["wo_number"]
