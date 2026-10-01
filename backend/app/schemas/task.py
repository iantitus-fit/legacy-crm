from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    job_id: Optional[int] = None
    title: str
    due_date: Optional[date] = None
    assigned_to_user_id: Optional[int] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[date] = None
    assigned_to_user_id: Optional[int] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None


class TaskResponse(BaseModel):
    id: int
    job_id: Optional[int] = None
    title: str
    status: str
    due_date: Optional[date] = None
    created_at: Optional[datetime] = None
    job_address: Optional[str] = None
    contact_name: Optional[str] = None
    is_overdue: bool = False
    assigned_to_user_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    related_entity_label: Optional[str] = None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int
    per_page: int
