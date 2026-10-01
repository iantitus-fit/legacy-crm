from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.user import User


class PriceList(Base):
    __tablename__ = "price_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_file: Mapped[Optional[str]] = mapped_column(String(255))
    effective_date: Mapped[Optional[date]] = mapped_column(Date())
    expiration_date: Mapped[Optional[date]] = mapped_column(Date())
    imported_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    imported_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id")
    )

    materials: Mapped[List["Material"]] = relationship(
        back_populates="price_list", cascade="all, delete-orphan"
    )
    imported_by: Mapped[Optional["User"]] = relationship()
