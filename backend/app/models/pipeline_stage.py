from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.lead import Lead
    from app.models.pipeline import Pipeline


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "name", name="uq_pipeline_stage_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("pipelines.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    is_closed_won: Mapped[bool] = mapped_column(
        Boolean(), server_default="false"
    )
    is_closed_lost: Mapped[bool] = mapped_column(
        Boolean(), server_default="false"
    )

    pipeline: Mapped["Pipeline"] = relationship(back_populates="stages")
    jobs: Mapped[List["Job"]] = relationship(back_populates="stage")
    leads: Mapped[List["Lead"]] = relationship(back_populates="stage")
