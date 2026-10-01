from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.change_order import ChangeOrder
    from app.models.crew import Crew
    from app.models.estimate_line_item import EstimateLineItem
    from app.models.estimate_section import EstimateSection
    from app.models.job import Job
    from app.models.pipeline import Pipeline
    from app.models.pipeline_stage import PipelineStage
    from app.models.user import User


class Estimate(Base):
    __tablename__ = "estimates"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("jobs.id")
    )
    name: Mapped[Optional[str]] = mapped_column(String(255))
    tax_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), server_default=text("0.0700")
    )
    subtotal: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    tax: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    show_quantities: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="true"
    )
    show_unit_prices: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="true"
    )
    show_line_totals: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="true"
    )
    show_subtotal: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="true"
    )
    tax_included: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="false"
    )
    deposit_percent: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", nullable=False
    )
    expiration_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id"), nullable=True
    )
    # Sprint 15a — job-phase fields (an approved estimate IS a job)
    job_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    work_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    location_address: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    crew_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("crews.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_start: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    scheduled_end: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pipeline_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("pipelines.id"), nullable=True
    )
    stage_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("pipeline_stages.id"), nullable=True
    )
    # Sprint 16b — AI-generated scope of work (free text, displayed on PDF)
    scope_of_work: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    # Sprint 20b — stamped on first work-order render as "WO-{id}"
    work_order_number: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job: Mapped[Optional["Job"]] = relationship(back_populates="estimates")
    crew: Mapped[Optional["Crew"]] = relationship("Crew", foreign_keys=[crew_id])
    assigned_to: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_to_user_id]
    )
    pipeline: Mapped[Optional["Pipeline"]] = relationship(
        "Pipeline", foreign_keys=[pipeline_id]
    )
    stage: Mapped[Optional["PipelineStage"]] = relationship(
        "PipelineStage", foreign_keys=[stage_id]
    )
    line_items: Mapped[List["EstimateLineItem"]] = relationship(
        back_populates="estimate"
    )
    sections: Mapped[List["EstimateSection"]] = relationship(
        back_populates="estimate"
    )
    change_orders: Mapped[List["ChangeOrder"]] = relationship(
        back_populates="estimate"
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[created_by_user_id]
    )
