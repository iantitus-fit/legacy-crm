from datetime import date, time
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class CalendarJobEvent(BaseModel):
    id: int
    display_name: Optional[str] = None
    contact_name: Optional[str] = None
    property_address: Optional[str] = None
    scheduled_date: Optional[date] = None
    scheduled_end_date: Optional[date] = None
    crew_id: Optional[int] = None
    crew_name: Optional[str] = None
    crew_color: Optional[str] = None
    stage_name: Optional[str] = None
    work_type: Optional[str] = None
    contract_value: Optional[Decimal] = None


class CalendarAppointmentEvent(BaseModel):
    id: int
    title: str
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    assigned_to_user_id: int
    assigned_to_name: Optional[str] = None
    assigned_to_color: Optional[str] = None
    appointment_date: date
    appointment_time: Optional[time] = None
    duration_minutes: int = 60
    location: Optional[str] = None
    appointment_type: str = "other"


class UpcomingItem(BaseModel):
    id: int
    item_type: str  # "job" or "appointment"
    title: str
    date: date
    time: Optional[time] = None
    color: Optional[str] = None
    link: str


class CalendarJobsResponse(BaseModel):
    items: List[CalendarJobEvent]


class CalendarAppointmentsResponse(BaseModel):
    items: List[CalendarAppointmentEvent]


class UpcomingResponse(BaseModel):
    items: List[UpcomingItem]
