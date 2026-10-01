from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.change_order import ChangeOrder


class ChangeOrderItem(Base):
    __tablename__ = "change_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    change_order_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("change_orders.id"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    line_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)

    change_order: Mapped["ChangeOrder"] = relationship(back_populates="items")
