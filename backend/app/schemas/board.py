"""Sprint 15c: Board response schemas for contact-centric and estimate-centric pipelines.

The legacy jobs-based pipeline board lives in schemas/job.py and is kept
unchanged during the transition. These new schemas shape responses for
Lead/Sales (contacts) and Jobs (approved estimates).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class ContactBoardCard(BaseModel):
    """Contact representation for Lead/Sales pipeline boards."""

    id: int
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    client_type: Optional[str] = None
    lead_source: Optional[str] = None
    stage_id: Optional[int] = None
    # Aggregates — sum of totals and count across this client's estimates
    estimate_count: int = 0
    active_estimate_value: Decimal = Decimal("0")
    last_activity_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactBoardStage(BaseModel):
    id: int
    name: str
    sort_order: int
    color: Optional[str] = None
    is_closed_won: bool
    is_closed_lost: bool
    contact_count: int
    total_value: Decimal
    contacts: List[ContactBoardCard]


class ContactBoardResponse(BaseModel):
    pipeline_id: int
    pipeline_name: str
    total_contacts: int
    total_value: Decimal
    stages: List[ContactBoardStage]


class EstimateBoardCard(BaseModel):
    """Estimate representation for the Jobs pipeline board."""

    id: int
    name: Optional[str] = None
    status: str
    job_type: Optional[str] = None
    work_type: Optional[str] = None
    location_address: Optional[str] = None
    total: Optional[Decimal] = None
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_company: Optional[str] = None
    crew_id: Optional[int] = None
    crew_name: Optional[str] = None
    crew_color: Optional[str] = None
    scheduled_start: Optional[date] = None
    scheduled_end: Optional[date] = None
    assigned_to_user_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    stage_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EstimateBoardStage(BaseModel):
    id: int
    name: str
    sort_order: int
    color: Optional[str] = None
    is_closed_won: bool
    is_closed_lost: bool
    estimate_count: int
    total_value: Decimal
    estimates: List[EstimateBoardCard]


class EstimateBoardResponse(BaseModel):
    pipeline_id: int
    pipeline_name: str
    total_estimates: int
    total_value: Decimal
    stages: List[EstimateBoardStage]
