from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.estimate_template_item import EstimateTemplateItem


class EstimateTemplate(Base):
    __tablename__ = "estimate_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    default_margin_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="46.00"
    )
    default_waste_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="10.00"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="true", nullable=False
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items: Mapped[List["EstimateTemplateItem"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )
