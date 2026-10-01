from datetime import date, datetime, time
from typing import List, Optional

from pydantic import BaseModel


class AppointmentCreate(BaseModel):
    title: str
    assigned_to_user_id: int
    appointment_date: date
    contact_id: Optional[int] = None
    appointment_time: Optional[time] = None
    duration_minutes: int = 60
    location: Optional[str] = None
    notes: Optional[str] = None
    appointment_type: str = "other"


class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    appointment_date: Optional[date] = None
    contact_id: Optional[int] = None
    appointment_time: Optional[time] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    appointment_type: Optional[str] = None


class AppointmentResponse(BaseModel):
    id: int
    title: str
    contact_id: Optional[int] = None
    assigned_to_user_id: int
    appointment_date: date
    appointment_time: Optional[time] = None
    duration_minutes: int = 60
    location: Optional[str] = None
    notes: Optional[str] = None
    appointment_type: str = "other"
    created_by_user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    contact_name: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_to_color: Optional[str] = None
    created_by_name: Optional[str] = None

    model_config = {"from_attributes": True}


class AppointmentListResponse(BaseModel):
    items: List[AppointmentResponse]
    total: int
    page: int
    per_page: int
