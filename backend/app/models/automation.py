"""Sprint 19a — automation engine ORM models.

Four tables back the drip / sequence system:

- ``AutomationSequence`` is a template definition with a trigger.
- ``AutomationStep`` is a single message within a sequence, ordered.
- ``AutomationEnrollment`` is a contact's live progression through a sequence.
- ``AutomationLog`` is the per-step send record (sent / skipped / failed).

The ``contacts.automations_enabled`` toggle lives on the ``Contact`` model.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.contact import Contact


class AutomationSequence(Base):
    __tablename__ = "automation_sequences"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_config: Mapped[Dict[str, Any]] = mapped_column(
        JSON(), nullable=False, default=dict
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="true", default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    steps: Mapped[List["AutomationStep"]] = relationship(
        "AutomationStep",
        back_populates="sequence",
        cascade="all, delete-orphan",
        order_by="AutomationStep.step_order",
    )
    enrollments: Mapped[List["AutomationEnrollment"]] = relationship(
        "AutomationEnrollment", back_populates="sequence"
    )


class AutomationStep(Base):
    __tablename__ = "automation_steps"
    __table_args__ = (
        UniqueConstraint(
            "sequence_id", "step_order", name="uq_automation_steps_seq_order"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sequence_id: Mapped[int] = mapped_column(
        Integer(),
        ForeignKey("automation_sequences.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_order: Mapped[int] = mapped_column(Integer(), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    delay_minutes: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default="0", default=0
    )
    template_body: Mapped[str] = mapped_column(Text(), nullable=False)
    template_subject: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    stop_on_reply: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="true", default=True
    )
    stop_on_stage_change: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="true", default=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="true", default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sequence: Mapped["AutomationSequence"] = relationship(
        "AutomationSequence", back_populates="steps"
    )


class AutomationEnrollment(Base):
    __tablename__ = "automation_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "sequence_id",
            "contact_id",
            name="uq_automation_enrollments_seq_contact",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sequence_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("automation_sequences.id"), nullable=False
    )
    contact_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("contacts.id"), nullable=False
    )
    current_step_order: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default="1", default=1
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active", default="active"
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_reason: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    next_step_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sequence: Mapped["AutomationSequence"] = relationship(
        "AutomationSequence", back_populates="enrollments"
    )
    contact: Mapped["Contact"] = relationship("Contact")
    logs: Mapped[List["AutomationLog"]] = relationship(
        "AutomationLog", back_populates="enrollment"
    )


class AutomationLog(Base):
    __tablename__ = "automation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        Integer(),
        ForeignKey("automation_enrollments.id"),
        nullable=False,
    )
    step_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("automation_steps.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    rendered_body: Mapped[str] = mapped_column(Text(), nullable=False)
    rendered_subject: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="pending",
        default="pending",
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    enrollment: Mapped["AutomationEnrollment"] = relationship(
        "AutomationEnrollment", back_populates="logs"
    )
    step: Mapped["AutomationStep"] = relationship("AutomationStep")
