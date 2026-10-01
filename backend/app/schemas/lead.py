from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class LeadCreate(BaseModel):
    """Lead capture - accepts inline contact info or existing contact_id."""
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    source: Optional[str] = None
    description: Optional[str] = None
    assigned_to_user_id: Optional[int] = None


class LeadUpdate(BaseModel):
    source: Optional[str] = None
    description: Optional[str] = None
    contact_id: Optional[int] = None
    stage_id: Optional[int] = None
    assigned_to_user_id: Optional[int] = None


class LeadResponse(BaseModel):
    id: int
    contact_id: Optional[int] = None
    stage_id: Optional[int] = None
    source: Optional[str] = None
    description: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    created_at: datetime
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    items: List[LeadResponse]
    total: int
    page: int
    per_page: int


class LeadConvertRequest(BaseModel):
    job_type: Optional[str] = None
    work_type: Optional[str] = None
    property_address: Optional[str] = None
    stage_id: Optional[int] = None


class LeadConvertResponse(BaseModel):
    job_id: int
    contact_id: int
