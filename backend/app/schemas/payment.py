from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    date_received: date
    amount: Decimal
    method: str
    reference: Optional[str] = None
    notes: Optional[str] = None
    is_deposit: bool = False
    send_receipt: bool = False
    receipt_email: Optional[str] = None


class PaymentUpdate(BaseModel):
    date_received: Optional[date] = None
    amount: Optional[Decimal] = None
    method: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    is_deposit: Optional[bool] = None


class PaymentResponse(BaseModel):
    id: int
    invoice_id: int
    date_received: date
    amount: Decimal
    method: str
    reference: Optional[str] = None
    notes: Optional[str] = None
    is_deposit: bool = False
    created_at: Optional[datetime] = None
    created_by: Optional[int] = None

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    items: List[PaymentResponse]


class ReceiptSendRequest(BaseModel):
    to_email: str
    subject: Optional[str] = None
    message: Optional[str] = None
