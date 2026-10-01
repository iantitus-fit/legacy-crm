from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("invoices.id"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    line_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(20), default="estimate", server_default="estimate", nullable=False
    )
    source_co_number: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    # Set on deposit_credit lines: the deposit invoice this line credits.
    source_invoice_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )

    invoice: Mapped["Invoice"] = relationship(
        back_populates="items", foreign_keys=[invoice_id]
    )
