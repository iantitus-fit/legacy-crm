from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.lead import Lead
    from app.models.pipeline import Pipeline
    from app.models.pipeline_stage import PipelineStage


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(2), server_default="IN")
    zip: Mapped[Optional[str]] = mapped_column(String(10))
    # Sprint 15a — client profile fields
    lead_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    client_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pipeline_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("pipelines.id"), nullable=True
    )
    stage_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("pipeline_stages.id"), nullable=True
    )
    # Sprint 16a — CSV import tracking + soft delete
    import_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    import_source_file: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # Sprint 17a — SMS opt-out
    sms_opt_out: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="false", default=False
    )
    sms_opt_out_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Sprint 19a — per-client automation kill switch
    automations_enabled: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="true", default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    jobs: Mapped[List["Job"]] = relationship(back_populates="contact")
    leads: Mapped[List["Lead"]] = relationship(back_populates="contact")
    pipeline: Mapped[Optional["Pipeline"]] = relationship(
        "Pipeline", foreign_keys=[pipeline_id]
    )
    stage: Mapped[Optional["PipelineStage"]] = relationship(
        "PipelineStage", foreign_keys=[stage_id]
    )
