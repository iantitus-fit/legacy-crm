from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class ChangeOrderItemCreate(BaseModel):
    description: str
    qty: Decimal
    unit_price: Decimal
    body: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None


class ChangeOrderItemUpdate(BaseModel):
    description: Optional[str] = None
    qty: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    body: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None


class ChangeOrderItemResponse(BaseModel):
    id: int
    change_order_id: int
    description: Optional[str] = None
    qty: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    line_total: Optional[Decimal] = None
    body: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None

    model_config = {"from_attributes": True}


class ChangeOrderCreate(BaseModel):
    name: Optional[str] = None


class ChangeOrderUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None


class ChangeOrderResponse(BaseModel):
    id: int
    estimate_id: int
    co_number: int
    name: Optional[str] = None
    status: str = "draft"
    subtotal: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    created_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    items: List[ChangeOrderItemResponse] = []

    model_config = {"from_attributes": True}
