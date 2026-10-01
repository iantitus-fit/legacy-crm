from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.invoice_item import InvoiceItem
    from app.models.estimate import Estimate
    from app.models.job import Job
    from app.models.payment import Payment
    from app.models.user import User


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("jobs.id"), nullable=False
    )
    estimate_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("estimates.id"), nullable=True
    )
    invoice_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", nullable=False
    )
    date_invoiced: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    tax: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    tax_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), server_default=text("0.0700")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    # Sprint 15a — deposit invoices can coexist with a final invoice
    is_deposit: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="false", nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id"), nullable=True
    )

    job: Mapped["Job"] = relationship(back_populates="invoices")
    estimate: Mapped[Optional["Estimate"]] = relationship()
    creator: Mapped[Optional["User"]] = relationship()
    items: Mapped[List["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        foreign_keys="InvoiceItem.invoice_id",
    )
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
