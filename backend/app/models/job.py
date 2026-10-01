from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.crew import Crew
    from app.models.document import Document
    from app.models.estimate import Estimate
    from app.models.invoice import Invoice
    from app.models.pipeline import Pipeline
    from app.models.pipeline_stage import PipelineStage
    from app.models.task import Task
    from app.models.user import User


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("pipelines.id"), nullable=False
    )
    contact_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("contacts.id")
    )
    stage_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("pipeline_stages.id")
    )
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id")
    )
    job_type: Mapped[Optional[str]] = mapped_column(String(50))
    work_type: Mapped[Optional[str]] = mapped_column(String(20))
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    notes: Mapped[Optional[str]] = mapped_column(Text())
    contract_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    lead_source: Mapped[Optional[str]] = mapped_column(String(100))
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    labels: Mapped[Optional[list]] = mapped_column(JSON(), nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    scheduled_end_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    crew_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("crews.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    pipeline: Mapped["Pipeline"] = relationship(back_populates="jobs")
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="jobs")
    stage: Mapped[Optional["PipelineStage"]] = relationship(back_populates="jobs")
    assigned_to: Mapped[Optional["User"]] = relationship()
    crew: Mapped[Optional["Crew"]] = relationship()
    estimates: Mapped[List["Estimate"]] = relationship(back_populates="job")
    invoices: Mapped[List["Invoice"]] = relationship(back_populates="job")
    tasks: Mapped[List["Task"]] = relationship(back_populates="job")
    documents: Mapped[List["Document"]] = relationship(back_populates="job")
