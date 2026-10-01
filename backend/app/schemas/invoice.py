from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class InvoiceItemCreate(BaseModel):
    description: str
    qty: Decimal
    unit_price: Decimal
    body: Optional[str] = None
    sort_order: Optional[int] = None
    source_type: str = "estimate"
    source_co_number: Optional[int] = None


class InvoiceItemUpdate(BaseModel):
    description: Optional[str] = None
    qty: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    body: Optional[str] = None
    sort_order: Optional[int] = None


class InvoiceItemResponse(BaseModel):
    id: int
    invoice_id: int
    description: Optional[str] = None
    qty: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    line_total: Optional[Decimal] = None
    body: Optional[str] = None
    sort_order: Optional[int] = None
    source_type: str = "estimate"
    source_co_number: Optional[int] = None
    source_invoice_id: Optional[int] = None

    model_config = {"from_attributes": True}


class InvoiceCreate(BaseModel):
    estimate_id: int


class InvoiceUpdate(BaseModel):
    notes: Optional[str] = None
    due_date: Optional[date] = None
    date_invoiced: Optional[date] = None
    status: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: int
    job_id: int
    estimate_id: Optional[int] = None
    invoice_number: str
    status: str = "draft"
    date_invoiced: Optional[date] = None
    due_date: Optional[date] = None
    subtotal: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    tax_rate: Optional[Decimal] = None
    total: Decimal = Decimal("0")
    amount_paid: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    is_deposit: bool = False
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[int] = None
    items: List[InvoiceItemResponse] = []
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    job_address: Optional[str] = None

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    items: List[InvoiceResponse]
    total: int
    page: int
    per_page: int


class InvoiceSendRequest(BaseModel):
    to_email: str
    subject: Optional[str] = None
    message: Optional[str] = None
