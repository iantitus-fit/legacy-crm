import logging
import os
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import (
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentUpdate,
    ReceiptSendRequest,
)
from app.utils.dependencies import get_current_user

logger = logging.getLogger("legacy_crm")

router = APIRouter(prefix="/api/invoices", tags=["payments"])

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)

TWO_PLACES = Decimal("0.01")


def recalculate_invoice_payments(db: Session, invoice_id: int):
    """Recalculate invoice amount_paid, balance, and status from payments."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return

    total_paid = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.invoice_id == invoice_id)
        .scalar()
    )
    invoice.amount_paid = Decimal(str(total_paid)).quantize(TWO_PLACES)
    invoice.balance = (invoice.total - invoice.amount_paid).quantize(TWO_PLACES)

    if invoice.status == "void":
        pass
    elif invoice.balance <= 0:
        invoice.status = "paid"
    elif invoice.amount_paid > 0:
        invoice.status = "partial"
    else:
        invoice.status = "sent" if invoice.date_invoiced else "draft"

    db.commit()


def _load_invoice_for_receipt(db: Session, invoice_id: int) -> Invoice:
    """Load invoice with job/contact for receipt context."""
    invoice = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.job).joinedload(Job.contact),
        )
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


def _send_receipt_email(db: Session, payment: Payment, to_email: str, subject: str = None, message: str = None):
    """Send a payment receipt email."""
    from app.services.email_service import send_email

    invoice = _load_invoice_for_receipt(db, payment.invoice_id)

    contact_name = None
    if invoice.job and invoice.job.contact:
        contact_name = invoice.job.contact.name

    invoice_number = invoice.invoice_number
    default_subject = f"Payment Receipt — {invoice_number}"

    template = jinja_env.get_template("payment_receipt_email.html")
    html = template.render(
        contact_name=contact_name,
        invoice_number=invoice_number,
        payment_date=payment.date_received,
        payment_amount=payment.amount,
        payment_method=payment.method,
        payment_reference=payment.reference,
        invoice_total=invoice.total,
        amount_paid=invoice.amount_paid,
        balance=invoice.balance,
        message=message,
        company_name="Legacy Roofing & Exteriors",
        company_phone="(615) 555-0100",
        company_email="info@legacy-roofing.example",
    )

    send_email(
        to_email=to_email,
        subject=subject or default_subject,
        html_body=html,
    )


# --- Payment CRUD ---


@router.post(
    "/{invoice_id}/payments",
    response_model=PaymentResponse,
    status_code=201,
)
def record_payment(
    invoice_id: int,
    data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status == "void":
        raise HTTPException(status_code=400, detail="Cannot record payment on a voided invoice")

    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")

    payment = Payment(
        invoice_id=invoice_id,
        date_received=data.date_received,
        amount=data.amount,
        method=data.method,
        reference=data.reference,
        notes=data.notes,
        is_deposit=data.is_deposit,
        created_by=current_user.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    recalculate_invoice_payments(db, invoice_id)

    # Fire-and-forget receipt email
    if data.send_receipt and data.receipt_email:
        try:
            _send_receipt_email(db, payment, data.receipt_email)
        except Exception:
            logger.exception("Failed to send payment receipt email (fire-and-forget)")

    db.refresh(payment)
    return payment


@router.get(
    "/{invoice_id}/payments",
    response_model=PaymentListResponse,
)
def list_payments(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    payments = (
        db.query(Payment)
        .filter(Payment.invoice_id == invoice_id)
        .order_by(Payment.date_received.asc(), Payment.id.asc())
        .all()
    )
    return PaymentListResponse(items=payments)


@router.put(
    "/{invoice_id}/payments/{payment_id}",
    response_model=PaymentResponse,
)
def update_payment(
    invoice_id: int,
    payment_id: int,
    data: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.invoice_id == invoice_id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    update_data = data.model_dump(exclude_unset=True)

    if "amount" in update_data and update_data["amount"] is not None:
        if update_data["amount"] <= 0:
            raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")

    for field, value in update_data.items():
        setattr(payment, field, value)

    db.commit()
    recalculate_invoice_payments(db, invoice_id)
    db.refresh(payment)
    return payment


@router.delete(
    "/{invoice_id}/payments/{payment_id}",
    status_code=204,
)
def delete_payment(
    invoice_id: int,
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.invoice_id == invoice_id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    db.delete(payment)
    db.commit()
    recalculate_invoice_payments(db, invoice_id)


# --- Send Receipt ---


@router.post(
    "/{invoice_id}/payments/{payment_id}/send-receipt",
)
def send_receipt(
    invoice_id: int,
    payment_id: int,
    data: ReceiptSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.invoice_id == invoice_id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    try:
        _send_receipt_email(db, payment, data.to_email, data.subject, data.message)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Failed to send receipt email")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    return {"success": True, "message": f"Receipt sent to {data.to_email}"}
