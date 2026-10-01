from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.estimate import Estimate
    from app.models.estimate_section import EstimateSection


class EstimateLineItem(Base):
    __tablename__ = "estimate_line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("estimates.id")
    )
    description: Mapped[Optional[str]] = mapped_column(String(500))
    qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    body: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    section_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("estimate_sections.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[Optional[int]] = mapped_column(Integer())

    estimate: Mapped[Optional["Estimate"]] = relationship(
        back_populates="line_items"
    )
    section: Mapped[Optional["EstimateSection"]] = relationship(
        back_populates="line_items"
    )
