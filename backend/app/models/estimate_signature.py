from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class EstimateSignature(Base):
    __tablename__ = "estimate_signatures"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("estimates.id"), nullable=False
    )
    signer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    signature_data: Mapped[str] = mapped_column(Text(), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True
    )
    terms_accepted: Mapped[bool] = mapped_column(
        Boolean(), default=False
    )
