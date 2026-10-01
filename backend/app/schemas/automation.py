"""Sprint 19b — Pydantic schemas for the automation API.

Mirrors the conventions used by app/schemas/estimate_template.py:
- ``model_config = {"from_attributes": True}`` on response schemas so SQLAlchemy
  ORM rows serialize directly.
- Optional fields on update schemas so ``model_dump(exclude_unset=True)``
  yields a clean partial-update payload.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
class StepCreate(BaseModel):
    step_order: Optional[int] = None
    channel: str  # 'sms' or 'email'
    delay_minutes: int = 0
    template_body: str
    template_subject: Optional[str] = None
    stop_on_reply: bool = True
    stop_on_stage_change: bool = True
    is_active: bool = True


class StepUpdate(BaseModel):
    step_order: Optional[int] = None
    channel: Optional[str] = None
    delay_minutes: Optional[int] = None
    template_body: Optional[str] = None
    template_subject: Optional[str] = None
    stop_on_reply: Optional[bool] = None
    stop_on_stage_change: Optional[bool] = None
    is_active: Optional[bool] = None


class StepResponse(BaseModel):
    id: int
    sequence_id: int
    step_order: int
    channel: str
    delay_minutes: int
    template_body: str
    template_subject: Optional[str] = None
    stop_on_reply: bool
    stop_on_stage_change: bool
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StepReorderItem(BaseModel):
    step_id: int
    step_order: int


class StepReorderRequest(BaseModel):
    items: List[StepReorderItem]


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------
class SequenceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    steps: List[StepCreate] = Field(default_factory=list)


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class SequenceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    steps: List[StepResponse] = Field(default_factory=list)
    step_count: int = 0
    active_enrollment_count: int = 0
    total_enrollment_count: int = 0

    model_config = {"from_attributes": True}


class SequenceListResponse(BaseModel):
    items: List[SequenceResponse]
    total: int


# ---------------------------------------------------------------------------
# Enrollments
# ---------------------------------------------------------------------------
class EnrollmentManualCreate(BaseModel):
    contact_id: int
    sequence_id: int


class EnrollmentStopRequest(BaseModel):
    reason: Optional[str] = None


class EnrollmentResponse(BaseModel):
    id: int
    sequence_id: int
    contact_id: int
    current_step_order: int
    status: str
    enrolled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    stopped_reason: Optional[str] = None
    next_step_at: Optional[datetime] = None
    sequence_name: Optional[str] = None
    contact_name: Optional[str] = None

    model_config = {"from_attributes": True}


class EnrollmentListResponse(BaseModel):
    items: List[EnrollmentResponse]
    total: int


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------
class AutomationLogResponse(BaseModel):
    id: int
    enrollment_id: int
    step_id: int
    channel: str
    rendered_body: str
    rendered_subject: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    sequence_name: Optional[str] = None
    contact_name: Optional[str] = None

    model_config = {"from_attributes": True}


class AutomationLogListResponse(BaseModel):
    items: List[AutomationLogResponse]
    total: int


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class DashboardActivityItem(BaseModel):
    log_id: int
    timestamp: Optional[datetime] = None
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    sequence_id: Optional[int] = None
    sequence_name: Optional[str] = None
    channel: str
    status: str


class DashboardResponse(BaseModel):
    active_sequences: int
    paused_sequences: int
    contacts_in_sequences: int
    messages_sent_7d: int
    messages_pending: int
    recent_activity: List[DashboardActivityItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Contact toggle
# ---------------------------------------------------------------------------
class ContactToggleRequest(BaseModel):
    automations_enabled: bool


class ContactToggleResponse(BaseModel):
    contact_id: int
    automations_enabled: bool
