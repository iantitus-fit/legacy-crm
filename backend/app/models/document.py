from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.estimate import Estimate
    from app.models.job import Job
    from app.models.user import User


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "(contact_id IS NOT NULL) OR (job_id IS NOT NULL) "
            "OR (estimate_id IS NOT NULL)",
            name="ck_documents_one_entity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("jobs.id"), nullable=True
    )
    contact_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("contacts.id"), nullable=True
    )
    # Sprint 20a — third polymorphic target so files can attach to an
    # estimate (which is the new client-facing "job" record).
    estimate_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("estimates.id", ondelete="CASCADE"), nullable=True
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer(), nullable=False)

    folder: Mapped[str] = mapped_column(
        String(100), nullable=False, default="General", server_default="General"
    )
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    is_photo: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=False, server_default="false"
    )
    show_in_work_order: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=False, server_default="false"
    )
    show_in_estimate: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=False, server_default="false"
    )

    uploaded_by: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    job: Mapped[Optional["Job"]] = relationship(back_populates="documents")
    contact: Mapped[Optional["Contact"]] = relationship("Contact")
    estimate: Mapped[Optional["Estimate"]] = relationship("Estimate")
    uploader: Mapped[Optional["User"]] = relationship("User", foreign_keys=[uploaded_by])
