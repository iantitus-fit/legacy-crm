from datetime import datetime, time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.user import User


class SmsMessage(Base):
    __tablename__ = "sms_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    from_number: Mapped[str] = mapped_column(String(20), nullable=False)
    to_number: Mapped[str] = mapped_column(String(20), nullable=False)
    twilio_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="queued", default="queued"
    )
    status_detail: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    sent_by: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    contact: Mapped["Contact"] = relationship("Contact")
    sender: Mapped[Optional["User"]] = relationship("User")


class SmsConfig(Base):
    __tablename__ = "sms_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    twilio_account_sid: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    twilio_auth_token_encrypted: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True
    )
    twilio_phone_number: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    auto_respond_new_lead: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="true", default=True
    )
    auto_respond_after_hours: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="true", default=True
    )
    business_hours_start: Mapped[time] = mapped_column(
        Time(), nullable=False, default=time(8, 0)
    )
    business_hours_end: Mapped[time] = mapped_column(
        Time(), nullable=False, default=time(18, 0)
    )
    business_timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="America/Indiana/Indianapolis",
        default="America/Indiana/Indianapolis",
    )
    new_lead_template: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default=(
            "Hi {first_name}, this is Legacy Roofing & Exteriors. "
            "We received your request and will be in touch shortly. "
            "Reply STOP to opt out."
        ),
    )
    after_hours_template: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default=(
            "Hi {first_name}, thanks for reaching out to Legacy Roofing "
            "& Exteriors. We're closed for the day but will call you "
            "first thing in the morning. Reply STOP to opt out."
        ),
    )
    estimate_sent_template: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default=(
            "Hi {first_name}, your estimate from Legacy Roofing is "
            "ready! View it here: {estimate_url} Reply STOP to opt out."
        ),
    )
    opt_out_keywords: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="STOP,UNSUBSCRIBE,CANCEL,END,QUIT",
    )
    opt_in_keywords: Mapped[str] = mapped_column(
        Text(), nullable=False, default="START,YES,UNSTOP"
    )
    help_response: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default=(
            "Legacy Roofing & Exteriors. Call us at (765) 555-0100 "
            "or visit legacy-roofing.example. Reply STOP to opt out."
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
