"""Sprint 6: employees, crews, task enhancements

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend users table with employee fields
    op.add_column("users", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("color", sa.String(7), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # 2. Create crews table
    op.create_table(
        "crews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # 3. Create crew_members association table
    op.create_table(
        "crew_members",
        sa.Column(
            "crew_id",
            sa.Integer(),
            sa.ForeignKey("crews.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # 4. Extend tasks table
    op.add_column(
        "tasks",
        sa.Column(
            "assigned_to_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column("related_entity_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("related_entity_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    # Drop task columns
    op.drop_column("tasks", "related_entity_id")
    op.drop_column("tasks", "related_entity_type")
    op.drop_column("tasks", "assigned_to_user_id")

    # Drop crew_members and crews
    op.drop_table("crew_members")
    op.drop_table("crews")

    # Drop user columns
    op.drop_column("users", "updated_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "color")
    op.drop_column("users", "phone")
