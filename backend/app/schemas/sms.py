from datetime import datetime, time
from typing import List, Optional

from pydantic import BaseModel, Field


class SmsMessageCreate(BaseModel):
    contact_id: int
    body: str
    triggered_by: Optional[str] = "manual"


class SmsSendRequest(BaseModel):
    contact_id: int
    body: str


class SmsSendEstimateRequest(BaseModel):
    contact_id: int
    estimate_id: int


class SmsMessageResponse(BaseModel):
    id: int
    contact_id: int
    contact_name: Optional[str] = None
    direction: str
    body: str
    from_number: str
    to_number: str
    twilio_sid: Optional[str] = None
    status: str
    status_detail: Optional[str] = None
    triggered_by: Optional[str] = None
    sent_by: Optional[int] = None
    sent_by_name: Optional[str] = None
    read_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SmsConversationResponse(BaseModel):
    items: List[SmsMessageResponse]
    total: int
    page: int
    per_page: int


class SmsConfigResponse(BaseModel):
    id: int
    twilio_account_sid: Optional[str] = None
    twilio_phone_number: Optional[str] = None
    auto_respond_new_lead: bool
    auto_respond_after_hours: bool
    business_hours_start: time
    business_hours_end: time
    business_timezone: str
    new_lead_template: str
    after_hours_template: str
    estimate_sent_template: str
    opt_out_keywords: str
    opt_in_keywords: str
    help_response: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SmsConfigUpdate(BaseModel):
    auto_respond_new_lead: Optional[bool] = None
    auto_respond_after_hours: Optional[bool] = None
    business_hours_start: Optional[time] = None
    business_hours_end: Optional[time] = None
    business_timezone: Optional[str] = None
    new_lead_template: Optional[str] = Field(default=None, max_length=1600)
    after_hours_template: Optional[str] = Field(default=None, max_length=1600)
    estimate_sent_template: Optional[str] = Field(default=None, max_length=1600)
    opt_out_keywords: Optional[str] = None
    opt_in_keywords: Optional[str] = None
    help_response: Optional[str] = Field(default=None, max_length=1600)
