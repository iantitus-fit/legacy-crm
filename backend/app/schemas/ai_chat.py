from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


VALID_ENTITY_TYPES = {"contact", "estimate"}


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    message: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    conversation_id: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    message: MessageResponse


class ConversationListItem(BaseModel):
    id: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    title: Optional[str] = None
    last_message_preview: Optional[str] = None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: List[ConversationListItem]
    total: int


class MessageListResponse(BaseModel):
    items: List[MessageResponse]
    total: int
    page: int
    per_page: int


class BriefingResponse(BaseModel):
    overdue_followups: List[Dict[str, Any]] = Field(default_factory=list)
    unsigned_estimates: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=lambda: {
            "viewed_not_signed": [],
            "not_viewed": [],
            "aging_over_5_days": [],
        }
    )
    overdue_invoices: List[Dict[str, Any]] = Field(default_factory=list)
    unpaid_invoices: List[Dict[str, Any]] = Field(default_factory=list)
    upcoming_appointments: List[Dict[str, Any]] = Field(default_factory=list)
    tasks_due: List[Dict[str, Any]] = Field(default_factory=list)
    recent_customer_actions: List[Dict[str, Any]] = Field(default_factory=list)
    overnight_ai_actions: List[Dict[str, Any]] = Field(default_factory=list)
    stale_leads: List[Dict[str, Any]] = Field(default_factory=list)
    summary_counts: Dict[str, int] = Field(default_factory=dict)
    generated_at: datetime


class NarrativeBriefingResponse(BaseModel):
    narrative: str
    data: BriefingResponse
    provider: str
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None


class Chip(BaseModel):
    label: str
    prompt: str


class ChipsResponse(BaseModel):
    items: List[Chip]
