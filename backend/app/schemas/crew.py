from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class CrewMemberResponse(BaseModel):
    id: int
    full_name: str
    color: Optional[str] = None

    model_config = {"from_attributes": True}


class CrewCreate(BaseModel):
    name: str
    color: str
    member_ids: Optional[List[int]] = None


class CrewUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    member_ids: Optional[List[int]] = None


class CrewResponse(BaseModel):
    id: int
    name: str
    color: str
    is_active: bool = True
    members: List[CrewMemberResponse] = []
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CrewListResponse(BaseModel):
    items: List[CrewResponse]
    total: int
    page: int
    per_page: int
