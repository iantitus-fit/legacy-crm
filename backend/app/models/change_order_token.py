from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ChangeOrderToken(Base):
    __tablename__ = "change_order_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    change_order_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("change_orders.id"), nullable=False
    )
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id"), nullable=True
    )
