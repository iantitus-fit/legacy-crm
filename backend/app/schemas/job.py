from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class JobCreate(BaseModel):
    pipeline_id: int
    contact_id: Optional[int] = None
    stage_id: Optional[int] = None
    job_type: Optional[str] = None
    work_type: Optional[str] = None
    property_address: Optional[str] = None
    notes: Optional[str] = None
    contract_value: Optional[Decimal] = None
    assigned_to_user_id: Optional[int] = None
    lead_source: Optional[str] = None
    display_name: Optional[str] = None
    labels: Optional[List[str]] = None
    scheduled_date: Optional[date] = None
    scheduled_end_date: Optional[date] = None
    crew_id: Optional[int] = None


class JobUpdate(BaseModel):
    contact_id: Optional[int] = None
    stage_id: Optional[int] = None
    job_type: Optional[str] = None
    work_type: Optional[str] = None
    property_address: Optional[str] = None
    notes: Optional[str] = None
    contract_value: Optional[Decimal] = None
    assigned_to_user_id: Optional[int] = None
    lead_source: Optional[str] = None
    display_name: Optional[str] = None
    labels: Optional[List[str]] = None
    scheduled_date: Optional[date] = None
    scheduled_end_date: Optional[date] = None
    crew_id: Optional[int] = None


class JobStageUpdate(BaseModel):
    """Lightweight schema for drag-and-drop stage changes."""
    stage_id: int


class JobPipelineMove(BaseModel):
    """Move a job to a different pipeline."""
    pipeline_id: int
    stage_id: Optional[int] = None


class JobScheduleUpdate(BaseModel):
    """Quick-schedule a job with date and optional crew."""
    scheduled_date: date
    scheduled_end_date: Optional[date] = None
    crew_id: Optional[int] = None


class JobResponse(BaseModel):
    id: int
    pipeline_id: int
    contact_id: Optional[int] = None
    stage_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None
    job_type: Optional[str] = None
    work_type: Optional[str] = None
    property_address: Optional[str] = None
    notes: Optional[str] = None
    contract_value: Optional[Decimal] = None
    lead_source: Optional[str] = None
    display_name: Optional[str] = None
    labels: Optional[List[str]] = None
    last_activity_at: Optional[datetime] = None
    scheduled_date: Optional[date] = None
    scheduled_end_date: Optional[date] = None
    crew_id: Optional[int] = None
    created_at: datetime
    contact_name: Optional[str] = None
    stage_name: Optional[str] = None
    pipeline_name: Optional[str] = None
    assigned_to_name: Optional[str] = None
    crew_name: Optional[str] = None
    crew_color: Optional[str] = None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    page: int
    per_page: int


class JobBoardCard(BaseModel):
    """Job representation for the pipeline board."""
    id: int
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    property_address: Optional[str] = None
    work_type: Optional[str] = None
    job_type: Optional[str] = None
    contract_value: Optional[Decimal] = None
    lead_source: Optional[str] = None
    display_name: Optional[str] = None
    labels: Optional[List[str]] = None
    assigned_to_user_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    stage_id: Optional[int] = None
    crew_id: Optional[int] = None
    crew_name: Optional[str] = None
    crew_color: Optional[str] = None
    scheduled_date: Optional[date] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BoardStage(BaseModel):
    id: int
    name: str
    sort_order: int
    color: Optional[str] = None
    is_closed_won: bool
    is_closed_lost: bool
    job_count: int
    total_value: Decimal
    jobs: List[JobBoardCard]


class PipelineBoardResponse(BaseModel):
    pipeline_id: int
    pipeline_name: str
    total_deals: int
    total_value: Decimal
    stages: List[BoardStage]
