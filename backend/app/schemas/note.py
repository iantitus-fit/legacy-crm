from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class NoteCreate(BaseModel):
    entity_type: str
    entity_id: int
    note_type: str
    content: str


class NoteUpdate(BaseModel):
    content: str


class NoteResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    note_type: str
    content: str
    created_by_user_id: int
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NoteListResponse(BaseModel):
    items: List[NoteResponse]
    total: int
    page: int
    per_page: int
