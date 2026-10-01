from datetime import date, datetime, time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.user import User


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("contacts.id", ondelete="SET NULL")
    )
    assigned_to_user_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("users.id"), nullable=False
    )
    appointment_date: Mapped[date] = mapped_column(Date(), nullable=False)
    appointment_time: Mapped[Optional[time]] = mapped_column(Time(), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default="60"
    )
    location: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    appointment_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="other"
    )
    created_by_user_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    contact: Mapped[Optional["Contact"]] = relationship()
    assigned_to: Mapped["User"] = relationship(foreign_keys=[assigned_to_user_id])
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])
