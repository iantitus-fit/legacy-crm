from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.change_order import ChangeOrderResponse


# --- Line Items ---


class EstimateLineItemCreate(BaseModel):
    description: str
    qty: Decimal
    unit_price: Decimal
    body: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None
    section_id: Optional[int] = None


class EstimateLineItemUpdate(BaseModel):
    description: Optional[str] = None
    qty: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    body: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None
    section_id: Optional[int] = None


class EstimateLineItemResponse(BaseModel):
    id: int
    estimate_id: Optional[int] = None
    description: Optional[str] = None
    qty: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    line_total: Optional[Decimal] = None
    body: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None
    section_id: Optional[int] = None

    model_config = {"from_attributes": True}


# --- Sections ---


class EstimateSectionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class EstimateSectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class EstimateSectionResponse(BaseModel):
    id: int
    estimate_id: int
    name: str
    description: Optional[str] = None
    sort_order: int = 0
    created_at: Optional[datetime] = None
    line_items: List[EstimateLineItemResponse] = []
    subtotal: Decimal = Decimal("0")

    model_config = {"from_attributes": True}


class SectionReorder(BaseModel):
    section_ids: List[int]


# --- Estimates ---


class EstimateCreate(BaseModel):
    job_id: int
    name: Optional[str] = ""
    tax_rate: Decimal = Decimal("0.0700")
    show_quantities: bool = True
    show_unit_prices: bool = True
    show_line_totals: bool = True
    show_subtotal: bool = True
    tax_included: bool = False
    deposit_percent: Optional[Decimal] = None
    expiration_date: Optional[date] = None
    # Sprint 15a — job-phase fields (an approved estimate IS a job)
    job_type: Optional[str] = None
    work_type: Optional[str] = None
    location_address: Optional[str] = None
    crew_id: Optional[int] = None
    scheduled_start: Optional[date] = None
    scheduled_end: Optional[date] = None
    assigned_to_user_id: Optional[int] = None
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None
    line_items: Optional[List[EstimateLineItemCreate]] = None


class EstimateUpdate(BaseModel):
    name: Optional[str] = None
    tax_rate: Optional[Decimal] = None
    show_quantities: Optional[bool] = None
    show_unit_prices: Optional[bool] = None
    show_line_totals: Optional[bool] = None
    show_subtotal: Optional[bool] = None
    tax_included: Optional[bool] = None
    deposit_percent: Optional[Decimal] = None
    expiration_date: Optional[date] = None
    # Sprint 15a — job-phase fields
    job_type: Optional[str] = None
    work_type: Optional[str] = None
    location_address: Optional[str] = None
    crew_id: Optional[int] = None
    scheduled_start: Optional[date] = None
    scheduled_end: Optional[date] = None
    assigned_to_user_id: Optional[int] = None
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None
    # Sprint 15d — job-phase status transitions
    # Accepts: draft/sent/viewed/approved/in_progress/complete/closed/rejected
    status: Optional[str] = None
    # Sprint 16b — AI-generated scope of work
    scope_of_work: Optional[str] = None


class EstimateResponse(BaseModel):
    id: int
    job_id: Optional[int] = None
    name: Optional[str] = None
    tax_rate: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    total: Optional[Decimal] = None
    show_quantities: bool = True
    show_unit_prices: bool = True
    show_line_totals: bool = True
    show_subtotal: bool = True
    tax_included: bool = False
    deposit_percent: Optional[Decimal] = None
    expiration_date: Optional[date] = None
    created_by_user_id: Optional[int] = None
    created_by_user_name: Optional[str] = None
    # Sprint 15a — job-phase fields
    job_type: Optional[str] = None
    work_type: Optional[str] = None
    location_address: Optional[str] = None
    crew_id: Optional[int] = None
    crew_name: Optional[str] = None
    crew_color: Optional[str] = None
    scheduled_start: Optional[date] = None
    scheduled_end: Optional[date] = None
    assigned_to_user_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None
    created_at: Optional[datetime] = None
    line_items: List[EstimateLineItemResponse] = []
    sections: List[EstimateSectionResponse] = []
    change_orders: List[ChangeOrderResponse] = []
    grand_total: Optional[Decimal] = None
    job_address: Optional[str] = None
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_company: Optional[str] = None
    contact_address: Optional[str] = None
    status: str = "draft"
    invoice_id: Optional[int] = None
    # Sprint 16b — AI-generated scope of work
    scope_of_work: Optional[str] = None

    model_config = {"from_attributes": True}


class EstimateListResponse(BaseModel):
    items: List[EstimateResponse]
    total: int
    page: int
    per_page: int


class LineItemReorder(BaseModel):
    item_ids: List[int]
