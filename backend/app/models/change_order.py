from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.change_order_item import ChangeOrderItem
    from app.models.estimate import Estimate
    from app.models.user import User


class ChangeOrder(Base):
    __tablename__ = "change_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("estimates.id"), nullable=False
    )
    co_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", nullable=False
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    tax: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id"), nullable=True
    )

    estimate: Mapped["Estimate"] = relationship(back_populates="change_orders")
    creator: Mapped[Optional["User"]] = relationship()
    items: Mapped[List["ChangeOrderItem"]] = relationship(
        back_populates="change_order", cascade="all, delete-orphan"
    )
