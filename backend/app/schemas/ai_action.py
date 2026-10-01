from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


VALID_EVENT_TYPES = {
    "lead_created",
    "follow_up_overdue",
    "estimate_approved",
    "job_completed",
    "estimate_created",
    "pre_visit_summary",
}


class GenerateRequest(BaseModel):
    event_type: str
    contact_id: Optional[int] = None
    estimate_id: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None


class AIActionResponse(BaseModel):
    id: str
    event_type: str
    contact_id: Optional[int]
    estimate_id: Optional[int]
    provider: str
    model: Optional[str]
    output: Optional[str]
    tokens_used: Optional[int]
    duration_ms: Optional[int]
    status: str
    error: Optional[str] = None
    used_at: Optional[datetime]
    created_at: datetime
    created_by: Optional[int]

    model_config = {"from_attributes": True}


class AIActionListResponse(BaseModel):
    items: List[AIActionResponse]
    total: int
    page: int
    per_page: int


class AIStatsResponse(BaseModel):
    total_actions: int
    completed: int
    failed: int
    used: int
    dismissed: int
    pending: int
    total_tokens: int
    by_event_type: Dict[str, int] = Field(default_factory=dict)
    by_provider: Dict[str, int] = Field(default_factory=dict)
