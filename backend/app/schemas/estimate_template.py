from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel


# --- Template Items ---


class TemplateItemCreate(BaseModel):
    material_id: Optional[int] = None
    description: str
    category: str
    unit_cost: Decimal
    uom: Optional[str] = None
    margin_pct: Optional[Decimal] = None
    waste_pct: Optional[Decimal] = None
    measurement_type: Optional[str] = None
    conversion_factor: Decimal = Decimal("1.0000")
    default_qty: Optional[Decimal] = None
    sort_order: Optional[int] = None


class TemplateItemUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    unit_cost: Optional[Decimal] = None
    uom: Optional[str] = None
    margin_pct: Optional[Decimal] = None
    waste_pct: Optional[Decimal] = None
    measurement_type: Optional[str] = None
    conversion_factor: Optional[Decimal] = None
    default_qty: Optional[Decimal] = None
    sort_order: Optional[int] = None


class TemplateItemResponse(BaseModel):
    id: int
    template_id: int
    material_id: Optional[int] = None
    description: str
    category: str
    unit_cost: Decimal
    uom: Optional[str] = None
    margin_pct: Decimal
    waste_pct: Decimal
    measurement_type: Optional[str] = None
    conversion_factor: Decimal
    default_qty: Optional[Decimal] = None
    sort_order: int

    model_config = {"from_attributes": True}


# --- Templates ---


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    default_margin_pct: Decimal = Decimal("46.00")
    default_waste_pct: Decimal = Decimal("10.00")


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_margin_pct: Optional[Decimal] = None
    default_waste_pct: Optional[Decimal] = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    default_margin_pct: Decimal
    default_waste_pct: Decimal
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    items: List[TemplateItemResponse] = []
    item_count: int = 0

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    items: List[TemplateResponse]
    total: int


class TemplateItemReorder(BaseModel):
    item_ids: List[int]


# --- Measurements & Preview ---


class MeasurementsInput(BaseModel):
    total_area: Optional[Decimal] = None
    ridge: Optional[Decimal] = None
    hip: Optional[Decimal] = None
    valley: Optional[Decimal] = None
    eave: Optional[Decimal] = None
    rake: Optional[Decimal] = None


class PreviewLineItem(BaseModel):
    description: str
    category: str
    qty: int
    unit_price: Decimal
    line_total: Decimal
    measurement_type: Optional[str] = None
    measurement_value: Optional[Decimal] = None
    raw_qty: Decimal
    waste_applied: Decimal
    uom: Optional[str] = None


class PreviewResponse(BaseModel):
    items: List[PreviewLineItem]
    subtotal: Decimal
    item_count: int


class PreviewRequest(BaseModel):
    measurements: MeasurementsInput


class ApplyTemplateRequest(BaseModel):
    template_id: int
    measurements: MeasurementsInput
