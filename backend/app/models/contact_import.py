from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ContactImport(Base):
    __tablename__ = "contact_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer(), default=0, nullable=False)
    field_mappings: Mapped[Optional[dict]] = mapped_column(JSON(), nullable=True)
    options: Mapped[Optional[dict]] = mapped_column(JSON(), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float(), nullable=True)
    undone_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
