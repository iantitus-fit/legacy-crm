from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.estimate_template import EstimateTemplate
    from app.models.material import Material


class EstimateTemplateItem(Base):
    __tablename__ = "estimate_template_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("estimate_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    material_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("materials.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    uom: Mapped[Optional[str]] = mapped_column(String(20))
    margin_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="46.00"
    )
    waste_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="10.00"
    )
    measurement_type: Mapped[Optional[str]] = mapped_column(String(50))
    conversion_factor: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default="1.0000"
    )
    default_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    sort_order: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default="0"
    )

    template: Mapped[Optional["EstimateTemplate"]] = relationship(
        back_populates="items"
    )
    material: Mapped[Optional["Material"]] = relationship()
