from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AIAction(Base):
    __tablename__ = "ai_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    estimate_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("estimates.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    user_prompt: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    output: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed", server_default="completed"
    )
    error: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
