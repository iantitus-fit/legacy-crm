import base64
import os
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.estimate_signature import EstimateSignature
from app.models.note import Note
from app.models.user import User
from app.routers.estimates import _estimate_to_response, _load_estimate
from app.utils.auth import decode_access_token
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/estimates", tags=["estimate-export"])

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)


def _build_template_context(estimate_data: dict, db: Session) -> dict:
    """Build the Jinja2 template context from an EstimateResponse dict."""
    # Load logo as base64 data URI
    logo_path = os.path.join(STATIC_DIR, "logo.png")
    logo_data_uri = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_bytes = f.read()
        logo_b64 = base64.b64encode(logo_bytes).decode("utf-8")
        logo_data_uri = f"data:image/png;base64,{logo_b64}"

    # Separate sectioned and unsectioned line items
    section_ids = {s["id"] for s in estimate_data.get("sections", [])}
    unsectioned_items = [
        li for li in estimate_data.get("line_items", [])
        if not getattr(li, "section_id", None) and not (
            isinstance(li, dict) and li.get("section_id")
        )
    ]

    # Compute totals
    subtotal = estimate_data.get("subtotal") or Decimal("0")
    tax_rate = estimate_data.get("tax_rate") or Decimal("0")
    tax_amount = estimate_data.get("tax") or Decimal("0")
    total = estimate_data.get("total") or Decimal("0")
    deposit_percent = estimate_data.get("deposit_percent")
    deposit_amount = Decimal("0")
    if deposit_percent:
        deposit_amount = (total * deposit_percent / Decimal("100")).quantize(
            Decimal("0.01")
        )

    # Load client notes for this estimate
    estimate_id = estimate_data["id"]
    client_notes = (
        db.query(Note)
        .filter(
            Note.entity_type == "estimate",
            Note.entity_id == estimate_id,
            Note.note_type == "client",
        )
        .order_by(Note.created_at)
        .all()
    )

    # Format line items (handle both ORM objects and dicts)
    def _li_to_dict(li):
        if isinstance(li, dict):
            return li
        return {
            "description": li.description,
            "qty": li.qty,
            "unit_price": li.unit_price,
            "line_total": li.line_total,
            "body": li.body,
            "section_id": li.section_id,
        }

    # Build sections with dict line items
    sections = []
    for s in estimate_data.get("sections", []):
        s_items = s.get("line_items", [])
        sections.append({
            "name": s.get("name", ""),
            "description": s.get("description"),
            "line_items": [_li_to_dict(li) for li in s_items],
            "subtotal": s.get("subtotal", Decimal("0")),
        })

    # Check for signature
    signature = (
        db.query(EstimateSignature)
        .filter(EstimateSignature.estimate_id == estimate_id)
        .first()
    )

    return {
        "signature_data": signature.signature_data if signature else None,
        "signer_name": signature.signer_name if signature else None,
        "signed_at": signature.signed_at if signature else None,
        "company_name": "Legacy Roofing & Exteriors",
        "company_address": "Franklin, TN",
        "company_phone": "(615) 555-0100",
        "company_email": "info@legacy-roofing.example",
        "logo_data_uri": logo_data_uri,
        "estimate_name": estimate_data.get("name", ""),
        "estimate_id": estimate_id,
        "created_at": estimate_data.get("created_at"),
        "expiration_date": estimate_data.get("expiration_date"),
        "contact_name": estimate_data.get("contact_name"),
        "job_address": estimate_data.get("job_address"),
        "show_quantities": estimate_data.get("show_quantities", True),
        "show_unit_prices": estimate_data.get("show_unit_prices", True),
        "show_line_totals": estimate_data.get("show_line_totals", True),
        "show_subtotal": estimate_data.get("show_subtotal", True),
        "tax_included": estimate_data.get("tax_included", False),
        "sections": sections,
        "unsectioned_items": [_li_to_dict(li) for li in unsectioned_items],
        "subtotal": subtotal,
        "tax_rate": tax_rate,
        "tax_rate_pct": (tax_rate * Decimal("100")).quantize(Decimal("0.01")),
        "tax_amount": tax_amount,
        "deposit_percent": deposit_percent,
        "deposit_amount": deposit_amount,
        "total": total,
        "client_notes": client_notes,
    }


def _render_estimate_html(estimate_id: int, db: Session) -> str:
    """Load estimate, build context, render template."""
    estimate = _load_estimate(db, estimate_id)
    estimate_data = _estimate_to_response(estimate)
    context = _build_template_context(estimate_data, db)
    template = jinja_env.get_template("estimate_pdf.html")
    return template.render(**context)


def _get_user_from_token_param(
    token: Optional[str], db: Session
) -> Optional[User]:
    """Validate a token query parameter and return the user."""
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    return db.query(User).filter(User.id == int(user_id)).first()


@router.get("/{estimate_id}/preview")
def preview_estimate(
    estimate_id: int,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    # Accept auth via token query param (for iframe loading)
    user = _get_user_from_token_param(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid token query parameter required",
        )
    html = _render_estimate_html(estimate_id, db)
    return HTMLResponse(content=html)


@router.get("/{estimate_id}/pdf")
def export_estimate_pdf(
    estimate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import traceback
    from weasyprint import HTML

    try:
        html = _render_estimate_html(estimate_id, db)
        estimate = _load_estimate(db, estimate_id)
        safe_name = (estimate.name or "Estimate").replace(" ", "_").encode("ascii", "ignore").decode()
        filename = f"Estimate_{safe_name}_{estimate_id}.pdf"
        pdf_bytes = HTML(string=html).write_pdf()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))