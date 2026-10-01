import logging
import os
from decimal import ROUND_HALF_UP, Decimal
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.change_order import ChangeOrder
from app.models.change_order_item import ChangeOrderItem
from app.models.change_order_token import ChangeOrderToken
from app.models.estimate import Estimate
from app.models.user import User
from app.schemas.change_order import (
    ChangeOrderCreate,
    ChangeOrderItemCreate,
    ChangeOrderItemResponse,
    ChangeOrderItemUpdate,
    ChangeOrderResponse,
    ChangeOrderUpdate,
)
from app.schemas.change_order_portal import COSendRequest
from app.services.email_service import send_email
from app.services.estimate_calculator import calculate_line_total
from app.utils.dependencies import get_current_user
from app.utils.portal_links import link_expiry

logger = logging.getLogger("legacy_crm")

TWO_PLACES = Decimal("0.01")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
co_jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)

router = APIRouter(tags=["change-orders"])


def _load_change_order(db: Session, co_id: int) -> ChangeOrder:
    co = (
        db.query(ChangeOrder)
        .options(joinedload(ChangeOrder.items))
        .filter(ChangeOrder.id == co_id)
        .first()
    )
    if not co:
        raise HTTPException(status_code=404, detail="Change order not found")
    return co


def _co_to_response(co: ChangeOrder) -> dict:
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
        "items": items,
    }


def recalculate_change_order(db: Session, co_id: int) -> None:
    co = (
        db.query(ChangeOrder)
        .options(joinedload(ChangeOrder.items))
        .filter(ChangeOrder.id == co_id)
        .first()
    )
    if not co:
        return
    estimate = db.query(Estimate).filter(Estimate.id == co.estimate_id).first()
    # Same rule as the parent estimate (services/estimate_calculator.py):
    # tax-included work carries no separate tax, and an explicit 0% stays 0%.
    if estimate.tax_included:
        tax_rate = Decimal("0")
    elif estimate.tax_rate is not None:
        tax_rate = Decimal(str(estimate.tax_rate))
    else:
        tax_rate = Decimal("0.07")
    subtotal = sum(
        (Decimal(str(item.line_total or 0)) for item in co.items),
        Decimal("0"),
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    tax = (subtotal * tax_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    co.subtotal = subtotal
    co.tax = tax
    co.total = (subtotal + tax).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    db.commit()


# --- Change Order CRUD ---


@router.post(
    "/api/estimates/{estimate_id}/change-orders",
    response_model=ChangeOrderResponse,
    status_code=201,
)
def create_change_order(
    estimate_id: int,
    data: ChangeOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    if estimate.status != "approved":
        raise HTTPException(
            status_code=400,
            detail="Change orders can only be created on approved estimates",
        )

    max_num = (
        db.query(func.max(ChangeOrder.co_number))
        .filter(ChangeOrder.estimate_id == estimate_id)
        .scalar()
    )
    co_number = (max_num or 0) + 1

    co = ChangeOrder(
        estimate_id=estimate_id,
        co_number=co_number,
        name=data.name,
        status="draft",
        created_by=current_user.id,
    )
    db.add(co)
    db.commit()
    db.refresh(co)

    return _co_to_response(co)


@router.get(
    "/api/estimates/{estimate_id}/change-orders",
    response_model=List[ChangeOrderResponse],
)
def list_change_orders(
    estimate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    cos = (
        db.query(ChangeOrder)
        .options(joinedload(ChangeOrder.items))
        .filter(ChangeOrder.estimate_id == estimate_id)
        .order_by(ChangeOrder.co_number)
        .all()
    )
    return [_co_to_response(co) for co in cos]


@router.get(
    "/api/change-orders/{co_id}",
    response_model=ChangeOrderResponse,
)
def get_change_order(
    co_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    co = _load_change_order(db, co_id)
    return _co_to_response(co)


@router.put(
    "/api/change-orders/{co_id}",
    response_model=ChangeOrderResponse,
)
def update_change_order(
    co_id: int,
    data: ChangeOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    co = _load_change_order(db, co_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(co, field, value)
    db.commit()
    co = _load_change_order(db, co_id)
    return _co_to_response(co)


@router.delete("/api/change-orders/{co_id}", status_code=204)
def delete_change_order(
    co_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    co = _load_change_order(db, co_id)
    db.delete(co)
    db.commit()


# --- Change Order Item CRUD ---


@router.post(
    "/api/change-orders/{co_id}/items",
    response_model=ChangeOrderItemResponse,
    status_code=201,
)
def add_co_item(
    co_id: int,
    data: ChangeOrderItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    co = _load_change_order(db, co_id)

    if data.sort_order is None:
        max_order = (
            db.query(ChangeOrderItem.sort_order)
            .filter(ChangeOrderItem.change_order_id == co_id)
            .order_by(ChangeOrderItem.sort_order.desc())
            .first()
        )
        sort_order = (max_order[0] or 0) + 1 if max_order else 0
    else:
        sort_order = data.sort_order

    item = ChangeOrderItem(
        change_order_id=co_id,
        description=data.description,
        qty=data.qty,
        unit_price=data.unit_price,
        line_total=calculate_line_total(data.qty, data.unit_price),
        body=data.body,
        notes=data.notes,
        sort_order=sort_order,
    )
    db.add(item)
    db.commit()
    recalculate_change_order(db, co_id)
    db.refresh(item)
    return item


@router.put(
    "/api/change-orders/{co_id}/items/{item_id}",
    response_model=ChangeOrderItemResponse,
)
def update_co_item(
    co_id: int,
    item_id: int,
    data: ChangeOrderItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(ChangeOrderItem)
        .filter(
            ChangeOrderItem.id == item_id,
            ChangeOrderItem.change_order_id == co_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Change order item not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()

    # Recalculate line_total
    qty = Decimal(str(item.qty or 0))
    unit_price = Decimal(str(item.unit_price or 0))
    item.line_total = calculate_line_total(qty, unit_price)
    db.commit()

    recalculate_change_order(db, co_id)
    db.refresh(item)
    return item


@router.delete("/api/change-orders/{co_id}/items/{item_id}", status_code=204)
def delete_co_item(
    co_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(ChangeOrderItem)
        .filter(
            ChangeOrderItem.id == item_id,
            ChangeOrderItem.change_order_id == co_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Change order item not found")

    db.delete(item)
    db.commit()
    recalculate_change_order(db, co_id)


@router.post(
    "/api/change-orders/{co_id}/items/{item_id}/duplicate",
    response_model=ChangeOrderItemResponse,
    status_code=201,
)
def duplicate_co_item(
    co_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = (
        db.query(ChangeOrderItem)
        .filter(
            ChangeOrderItem.id == item_id,
            ChangeOrderItem.change_order_id == co_id,
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Change order item not found")

    max_order = (
        db.query(ChangeOrderItem.sort_order)
        .filter(ChangeOrderItem.change_order_id == co_id)
        .order_by(ChangeOrderItem.sort_order.desc())
        .first()
    )
    new_sort_order = (max_order[0] or 0) + 1 if max_order else 0

    duplicate = ChangeOrderItem(
        change_order_id=co_id,
        description=source.description,
        qty=source.qty,
        unit_price=source.unit_price,
        line_total=calculate_line_total(source.qty, source.unit_price),
        body=source.body,
        notes=source.notes,
        sort_order=new_sort_order,
    )
    db.add(duplicate)
    db.commit()

    recalculate_change_order(db, co_id)
    db.refresh(duplicate)
    return duplicate


# --- Send CO ---


@router.post("/api/change-orders/{co_id}/send")
def send_change_order(
    co_id: int,
    data: COSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    co = _load_change_order(db, co_id)
    estimate = db.query(Estimate).filter(Estimate.id == co.estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Parent estimate not found")

    # Build context for email
    from app.models.job import Job
    from app.models.contact import Contact

    contact_name = None
    if estimate.job_id:
        job = db.query(Job).filter(Job.id == estimate.job_id).first()
        if job and job.contact_id:
            contact = db.query(Contact).filter(Contact.id == job.contact_id).first()
            if contact:
                contact_name = contact.name

    subject = data.subject or f"Change Order #{co.co_number} from Legacy Roofing & Exteriors"
    message = data.message or (
        f"Please review the attached change order for {estimate.name or 'your project'}."
    )

    # Create portal token and build URL
    token_value = uuid4().hex
    portal_base = os.environ.get("PORTAL_BASE_URL", "http://localhost:5173")
    portal_url = f"{portal_base}/portal/co/{token_value}"

    # Render email body
    email_template = co_jinja_env.get_template("change_order_email.html")
    email_html = email_template.render(
        contact_name=contact_name,
        co_number=co.co_number,
        co_name=co.name,
        estimate_name=estimate.name or "Estimate",
        message=message,
        portal_url=portal_url,
        company_name="Legacy Roofing & Exteriors",
        company_phone="(615) 555-0100",
        company_email="info@legacy-roofing.example",
    )

    # Generate PDF
    from app.routers.change_order_portal import _render_co_html

    pdf_html = _render_co_html(co, db)
    safe_name = (co.name or "ChangeOrder").replace(" ", "_").encode("ascii", "ignore").decode()
    filename = f"ChangeOrder_{co.co_number}_{safe_name}.pdf"

    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=pdf_html).write_pdf()
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
        logger.exception("Failed to send change order email")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    # Create token and update status
    db.add(ChangeOrderToken(
        change_order_id=co.id,
        token=token_value,
        created_by=current_user.id,
        expires_at=link_expiry(),
    ))
    co.status = "sent"
    db.commit()

    return {"success": True, "message": f"Change order sent to {data.to_email}"}
