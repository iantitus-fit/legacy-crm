from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.estimate import Estimate
    from app.models.estimate_line_item import EstimateLineItem


class EstimateSection(Base):
    __tablename__ = "estimate_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer(), server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    estimate: Mapped["Estimate"] = relationship(back_populates="sections")
    line_items: Mapped[List["EstimateLineItem"]] = relationship(
        back_populates="section"
    )
