import logging
import os
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.change_order import ChangeOrder
from app.models.change_order_item import ChangeOrderItem
from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.estimate_line_item import EstimateLineItem
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.job import Job
from app.models.user import User
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceItemCreate,
    InvoiceItemResponse,
    InvoiceItemUpdate,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceSendRequest,
    InvoiceUpdate,
)
from app.services.estimate_calculator import calculate_line_total
from app.utils.dependencies import get_current_user

logger = logging.getLogger("legacy_crm")

router = APIRouter(prefix="/api/invoices", tags=["invoices"])

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)

TWO_PLACES = Decimal("0.01")


DEPOSIT_CREDIT = "deposit_credit"
MANUAL_STATUSES = {"draft", "sent", "void"}


def _next_invoice_number(db: Session) -> str:
    """Next INV-#### number: one past the highest INV number on file.

    Imported AccuLynx invoices keep their own numbers (e.g. "1004-1"), so the
    sequence reads only INV- numbers instead of whatever row came last.
    """
    highest = 0
    for (number,) in db.query(Invoice.invoice_number).filter(
        Invoice.invoice_number.like("INV-%")
    ):
        suffix = number[4:]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"INV-{highest + 1:04d}"


def _recalculate_invoice(db: Session, invoice_id: int):
    """Recalculate subtotal, tax, total, balance from line items."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return

    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).all()

    # Recalc each line_total
    for item in items:
        qty = Decimal(str(item.qty or 0))
        unit_price = Decimal(str(item.unit_price or 0))
        item.line_total = calculate_line_total(qty, unit_price)

    # Deposit credits are post-tax dollars (the deposit invoice carried no
    # tax), so they come off after tax rather than out of the taxable subtotal.
    credits = sum(
        (Decimal(str(item.line_total or 0)) for item in items if item.source_type == DEPOSIT_CREDIT),
        Decimal("0"),
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    subtotal = sum(
        (Decimal(str(item.line_total or 0)) for item in items if item.source_type != DEPOSIT_CREDIT),
        Decimal("0"),
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Respect an explicit tax_rate of 0 (e.g. deposit invoices); only
    # fall back to 7% when the column is NULL.
    tax_rate = Decimal(str(invoice.tax_rate)) if invoice.tax_rate is not None else Decimal("0.07")
    tax = (subtotal * tax_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    total = (subtotal + tax + credits).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    invoice.subtotal = subtotal
    invoice.tax = tax
    invoice.total = total
    invoice.balance = total - Decimal(str(invoice.amount_paid or 0))
    db.commit()


def _load_invoice(db: Session, invoice_id: int) -> Invoice:
    """Load an invoice with all relationships."""
    invoice = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.items),
            joinedload(Invoice.job).joinedload(Job.contact),
            joinedload(Invoice.estimate),
            joinedload(Invoice.creator),
        )
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


def _invoice_to_response(invoice: Invoice) -> dict:
    """Build an InvoiceResponse dict with computed fields."""
    items = sorted(invoice.items, key=lambda i: i.sort_order or 0)

    contact_name = None
    contact_email = None
    contact_phone = None
    job_address = None
    if invoice.job:
        job_address = invoice.job.property_address
        if invoice.job.contact:
            contact_name = invoice.job.contact.name
            contact_email = invoice.job.contact.email
            contact_phone = invoice.job.contact.phone

    return {
        "id": invoice.id,
        "job_id": invoice.job_id,
        "estimate_id": invoice.estimate_id,
        "invoice_number": invoice.invoice_number,
        "status": invoice.status,
        "date_invoiced": invoice.date_invoiced,
        "due_date": invoice.due_date,
        "subtotal": invoice.subtotal,
        "tax": invoice.tax,
        "tax_rate": invoice.tax_rate,
        "total": invoice.total,
        "amount_paid": invoice.amount_paid,
        "balance": invoice.balance,
        "is_deposit": bool(invoice.is_deposit),
        "notes": invoice.notes,
        "created_at": invoice.created_at,
        "created_by": invoice.created_by,
        "items": items,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "job_address": job_address,
    }


# --- Invoice CRUD ---


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    data: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Load estimate with line items and change orders
    estimate = (
        db.query(Estimate)
        .options(
            joinedload(Estimate.line_items),
            joinedload(Estimate.job),
            joinedload(Estimate.change_orders).joinedload(ChangeOrder.items),
        )
        .filter(Estimate.id == data.estimate_id)
        .first()
    )
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    if estimate.status != "approved":
        raise HTTPException(status_code=400, detail="Estimate must be approved to create an invoice")

    # Check for duplicate final invoice (deposit invoices can coexist)
    existing = (
        db.query(Invoice)
        .filter(
            Invoice.estimate_id == data.estimate_id,
            Invoice.is_deposit == False,  # noqa: E712
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Invoice already exists for this estimate")

    invoice_number = _next_invoice_number(db)

    invoice_tax_rate = Decimal("0") if estimate.tax_included else estimate.tax_rate
    invoice = Invoice(
        job_id=estimate.job_id,
        estimate_id=estimate.id,
        invoice_number=invoice_number,
        status="draft",
        tax_rate=invoice_tax_rate,
        subtotal=Decimal("0"),
        tax=Decimal("0"),
        total=Decimal("0"),
        amount_paid=Decimal("0"),
        balance=Decimal("0"),
        created_by=current_user.id,
    )
    db.add(invoice)
    db.flush()

    sort_idx = 0

    # Copy estimate line items
    for li in sorted(estimate.line_items, key=lambda x: x.sort_order or 0):
        item = InvoiceItem(
            invoice_id=invoice.id,
            description=li.description,
            qty=li.qty,
            unit_price=li.unit_price,
            line_total=li.line_total,
            body=li.body,
            sort_order=sort_idx,
            source_type="estimate",
        )
        db.add(item)
        sort_idx += 1

    # Copy approved change order items
    for co in sorted(estimate.change_orders or [], key=lambda c: c.co_number):
        if co.status != "approved":
            continue
        for ci in sorted(co.items, key=lambda x: x.sort_order or 0):
            item = InvoiceItem(
                invoice_id=invoice.id,
                description=ci.description,
                qty=ci.qty,
                unit_price=ci.unit_price,
                line_total=ci.line_total,
                body=ci.body,
                sort_order=sort_idx,
                source_type="change_order",
                source_co_number=co.co_number,
            )
            db.add(item)
            sort_idx += 1

    # Credit every deposit already billed for this estimate, so the final
    # invoice asks only for what is left.
    deposits = (
        db.query(Invoice)
        .filter(
            Invoice.estimate_id == estimate.id,
            Invoice.is_deposit == True,  # noqa: E712
            Invoice.status != "void",
        )
        .order_by(Invoice.id)
        .all()
    )
    for deposit in deposits:
        credit = -Decimal(str(deposit.total or 0))
        db.add(InvoiceItem(
            invoice_id=invoice.id,
            description=f"Less deposit invoice {deposit.invoice_number}",
            qty=Decimal("1"),
            unit_price=credit,
            line_total=credit,
            sort_order=sort_idx,
            source_type=DEPOSIT_CREDIT,
            source_invoice_id=deposit.id,
        ))
        sort_idx += 1

    db.commit()
    _recalculate_invoice(db, invoice.id)

    invoice = _load_invoice(db, invoice.id)
    return _invoice_to_response(invoice)


# --- Sprint 15a: Deposit invoices ---


class DepositInvoiceRequest(BaseModel):
    estimate_id: int
    deposit_percent: Decimal = Decimal("50")


@router.post(
    "/deposit",
    response_model=InvoiceResponse,
    status_code=201,
)
def create_deposit_invoice(
    data: DepositInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a deposit invoice from an estimate without changing status.

    Deposit invoices can be sent before the customer formally approves
    the estimate. The resulting invoice has a single line item
    representing the deposit portion of the estimate total, is_deposit
    is True, and the parent estimate stays in its current status.
    """
    estimate = (
        db.query(Estimate)
        .options(joinedload(Estimate.job))
        .filter(Estimate.id == data.estimate_id)
        .first()
    )
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    if data.deposit_percent <= 0 or data.deposit_percent >= 100:
        raise HTTPException(
            status_code=400,
            detail="deposit_percent must be between 0 and 100 (exclusive)",
        )

    total = Decimal(str(estimate.total or 0))
    if total <= 0:
        raise HTTPException(
            status_code=400,
            detail="Estimate must have a positive total before creating a deposit invoice",
        )

    final_exists = (
        db.query(Invoice)
        .filter(
            Invoice.estimate_id == estimate.id,
            Invoice.is_deposit == False,  # noqa: E712
            Invoice.status != "void",
        )
        .first()
    )
    if final_exists:
        raise HTTPException(
            status_code=400,
            detail="A final invoice already exists for this estimate. Adjust that invoice instead.",
        )
    deposit_amount = (total * data.deposit_percent / Decimal("100")).quantize(
        Decimal("0.01")
    )

    invoice_number = _next_invoice_number(db)
    invoice = Invoice(
        job_id=estimate.job_id,
        estimate_id=estimate.id,
        invoice_number=invoice_number,
        status="draft",
        tax_rate=Decimal("0"),  # deposit already represents post-tax dollars
        subtotal=Decimal("0"),
        tax=Decimal("0"),
        total=Decimal("0"),
        amount_paid=Decimal("0"),
        balance=Decimal("0"),
        is_deposit=True,
        created_by=current_user.id,
    )
    db.add(invoice)
    db.flush()

    description = f"Deposit — {data.deposit_percent}% of estimate {estimate.name or f'#{estimate.id}'}"
    db.add(
        InvoiceItem(
            invoice_id=invoice.id,
            description=description,
            qty=Decimal("1"),
            unit_price=deposit_amount,
            line_total=deposit_amount,
            sort_order=0,
            source_type="deposit",
        )
    )

    db.commit()
    _recalculate_invoice(db, invoice.id)

    invoice = _load_invoice(db, invoice.id)
    return _invoice_to_response(invoice)


@router.get("", response_model=InvoiceListResponse)
def list_invoices(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    estimate_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Invoice).options(
        joinedload(Invoice.items),
        joinedload(Invoice.job).joinedload(Job.contact),
        joinedload(Invoice.estimate),
        joinedload(Invoice.creator),
    )

    if estimate_id is not None:
        query = query.filter(Invoice.estimate_id == estimate_id)

    if status:
        query = query.filter(Invoice.status == status)

    if search:
        pattern = f"%{search}%"
        query = query.join(Job, Invoice.job_id == Job.id, isouter=True).join(
            Contact, Job.contact_id == Contact.id, isouter=True
        )
        query = query.filter(
            or_(
                Invoice.invoice_number.ilike(pattern),
                Job.property_address.ilike(pattern),
                Contact.name.ilike(pattern),
            )
        )

    total = query.count()

    items = (
        query.order_by(Invoice.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return InvoiceListResponse(
        items=[_invoice_to_response(inv) for inv in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = _load_invoice(db, invoice_id)
    return _invoice_to_response(invoice)


@router.put("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: int,
    data: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    update_data = data.model_dump(exclude_unset=True)
    new_status = update_data.get("status")
    if new_status is not None and new_status not in MANUAL_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid invoice status '{new_status}'. Set draft, sent or void; "
                "partial and paid follow from recorded payments."
            ),
        )
    voiding_deposit = (
        new_status == "void" and invoice.is_deposit and invoice.status != "void"
    )
    for field, value in update_data.items():
        setattr(invoice, field, value)

    db.commit()

    if voiding_deposit:
        _remove_deposit_credits(db, invoice.id)

    invoice = _load_invoice(db, invoice_id)
    return _invoice_to_response(invoice)


def _remove_deposit_credits(db: Session, deposit_invoice_id: int) -> None:
    """A voided deposit no longer reduces the final invoice that credited it."""
    from app.routers.payments import recalculate_invoice_payments

    credit_lines = (
        db.query(InvoiceItem)
        .filter(
            InvoiceItem.source_invoice_id == deposit_invoice_id,
            InvoiceItem.source_type == DEPOSIT_CREDIT,
        )
        .all()
    )
    affected = {line.invoice_id for line in credit_lines}
    for line in credit_lines:
        db.delete(line)
    db.commit()
    for invoice_id in affected:
        _recalculate_invoice(db, invoice_id)
        recalculate_invoice_payments(db, invoice_id)


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft invoices can be deleted")

    db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).delete()
    db.delete(invoice)
    db.commit()


# --- Invoice Item CRUD ---


@router.post(
    "/{invoice_id}/items",
    response_model=InvoiceItemResponse,
    status_code=201,
)
def add_invoice_item(
    invoice_id: int,
    data: InvoiceItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if data.sort_order is None:
        max_order = (
            db.query(InvoiceItem.sort_order)
            .filter(InvoiceItem.invoice_id == invoice_id)
            .order_by(InvoiceItem.sort_order.desc())
            .first()
        )
        sort_order = (max_order[0] or 0) + 1 if max_order else 0
    else:
        sort_order = data.sort_order

    item = InvoiceItem(
        invoice_id=invoice_id,
        description=data.description,
        qty=data.qty,
        unit_price=data.unit_price,
        line_total=calculate_line_total(data.qty, data.unit_price),
        body=data.body,
        sort_order=sort_order,
        source_type=data.source_type,
        source_co_number=data.source_co_number,
    )
    db.add(item)
    db.commit()

    _recalculate_invoice(db, invoice_id)
    db.refresh(item)
    return item


@router.put(
    "/{invoice_id}/items/{item_id}",
    response_model=InvoiceItemResponse,
)
def update_invoice_item(
    invoice_id: int,
    item_id: int,
    data: InvoiceItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(InvoiceItem)
        .filter(
            InvoiceItem.id == item_id,
            InvoiceItem.invoice_id == invoice_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Invoice item not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    _recalculate_invoice(db, invoice_id)
    db.refresh(item)
    return item


@router.delete("/{invoice_id}/items/{item_id}", status_code=204)
def delete_invoice_item(
    invoice_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(InvoiceItem)
        .filter(
            InvoiceItem.id == item_id,
            InvoiceItem.invoice_id == invoice_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Invoice item not found")

    db.delete(item)
    db.commit()
    _recalculate_invoice(db, invoice_id)


# --- PDF ---


import base64


def _build_invoice_pdf_context(invoice_data: dict) -> dict:
    """Build Jinja2 template context for invoice PDF."""
    logo_path = os.path.join(STATIC_DIR, "logo.png")
    logo_data_uri = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("utf-8")
        logo_data_uri = f"data:image/png;base64,{logo_b64}"

    subtotal = invoice_data.get("subtotal") or Decimal("0")
    tax_rate = invoice_data.get("tax_rate") or Decimal("0")
    tax_amount = invoice_data.get("tax") or Decimal("0")
    total = invoice_data.get("total") or Decimal("0")
    amount_paid = invoice_data.get("amount_paid") or Decimal("0")
    balance = invoice_data.get("balance") or Decimal("0")

    # Format items for template
    items = []
    credits = []
    for item in invoice_data.get("items", []):
        if isinstance(item, dict):
            items.append(item)
        else:
            items.append({
                "description": item.description,
                "qty": item.qty,
                "unit_price": item.unit_price,
                "line_total": item.line_total,
                "body": item.body,
                "source_type": item.source_type,
                "source_co_number": item.source_co_number,
                "source_invoice_id": item.source_invoice_id,
            })

    credits = [i for i in items if i.get("source_type") == DEPOSIT_CREDIT]
    items = [i for i in items if i.get("source_type") != DEPOSIT_CREDIT]

    return {
        "company_name": "Legacy Roofing & Exteriors",
        "company_address": "Franklin, TN",
        "company_phone": "(615) 555-0100",
        "company_email": "info@legacy-roofing.example",
        "logo_data_uri": logo_data_uri,
        "invoice_number": invoice_data.get("invoice_number", ""),
        "status": invoice_data.get("status", "draft"),
        "date_invoiced": invoice_data.get("date_invoiced"),
        "due_date": invoice_data.get("due_date"),
        "contact_name": invoice_data.get("contact_name"),
        "contact_email": invoice_data.get("contact_email"),
        "contact_phone": invoice_data.get("contact_phone"),
        "job_address": invoice_data.get("job_address"),
        "items": items,
        "credits": credits,
        "subtotal": subtotal,
        "tax_rate": tax_rate,
        "tax_rate_pct": (Decimal(str(tax_rate)) * Decimal("100")).quantize(Decimal("0.01")),
        "tax_amount": tax_amount,
        "total": total,
        "amount_paid": amount_paid,
        "balance": balance,
        "notes": invoice_data.get("notes"),
    }


def _render_invoice_html(invoice_id: int, db: Session) -> str:
    """Load invoice, build context, render template."""
    invoice = _load_invoice(db, invoice_id)
    invoice_data = _invoice_to_response(invoice)
    context = _build_invoice_pdf_context(invoice_data)
    template = jinja_env.get_template("invoice_pdf.html")
    return template.render(**context)


@router.get("/{invoice_id}/pdf")
def export_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import traceback
    from weasyprint import HTML

    try:
        html = _render_invoice_html(invoice_id, db)
        invoice = _load_invoice(db, invoice_id)
        filename = f"Invoice_{invoice.invoice_number}.pdf"
        pdf_bytes = HTML(string=html).write_pdf()
        from fastapi.responses import Response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Send Invoice ---


@router.post("/{invoice_id}/send")
def send_invoice_email(
    invoice_id: int,
    data: InvoiceSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = _load_invoice(db, invoice_id)
    invoice_data = _invoice_to_response(invoice)

    contact_name = invoice_data.get("contact_name")
    invoice_number = invoice_data.get("invoice_number", "Invoice")

    subject = data.subject or f"Invoice {invoice_number} from Legacy Roofing & Exteriors"
    message = data.message or "Please find attached your invoice from Legacy Roofing & Exteriors."

    # Render email
    email_template = jinja_env.get_template("invoice_email.html")
    email_html = email_template.render(
        contact_name=contact_name,
        invoice_number=invoice_number,
        message=message,
        company_name="Legacy Roofing & Exteriors",
        company_phone="(615) 555-0100",
        company_email="info@legacy-roofing.example",
    )

    # Generate PDF
    from weasyprint import HTML
    pdf_html = _render_invoice_html(invoice_id, db)
    filename = f"Invoice_{invoice_number}.pdf"
    pdf_bytes = HTML(string=pdf_html).write_pdf()

    # Send
    from app.services.email_service import send_email
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
        logger.exception("Failed to send invoice email")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    # Update status
    invoice.status = "sent"
    if not invoice.date_invoiced:
        invoice.date_invoiced = date.today()
    db.commit()

    return {"success": True, "message": f"Invoice sent to {data.to_email}"}
