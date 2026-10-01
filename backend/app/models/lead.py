from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.pipeline_stage import PipelineStage


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("contacts.id")
    )
    stage_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("pipeline_stages.id")
    )
    source: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text())
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    contact: Mapped[Optional["Contact"]] = relationship(back_populates="leads")
    stage: Mapped[Optional["PipelineStage"]] = relationship(back_populates="leads")
