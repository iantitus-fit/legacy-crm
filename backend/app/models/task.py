from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.user import User


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("jobs.id")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="open")
    due_date: Mapped[Optional[date]] = mapped_column(Date())
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id")
    )
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(20))
    related_entity_id: Mapped[Optional[int]] = mapped_column(Integer())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job: Mapped[Optional["Job"]] = relationship(back_populates="tasks")
    assigned_to: Mapped[Optional["User"]] = relationship(back_populates="assigned_tasks")
