from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class ContactCreate(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: str = "IN"
    zip: Optional[str] = None
    # Sprint 15a — client profile fields
    lead_source: Optional[str] = None
    client_type: Optional[str] = None  # 'residential' | 'commercial'
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    lead_source: Optional[str] = None
    client_type: Optional[str] = None
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None


class ContactResponse(BaseModel):
    id: int
    name: str
    company: Optional[str] = None
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]
    lead_source: Optional[str] = None
    client_type: Optional[str] = None
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None
    sms_opt_out: bool = False
    sms_opt_out_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactListResponse(BaseModel):
    items: List[ContactResponse]
    total: int
    page: int
    per_page: int


class ContactSearchResult(BaseModel):
    id: int
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    client_type: Optional[str] = None
    lead_source: Optional[str] = None

    model_config = {"from_attributes": True}
