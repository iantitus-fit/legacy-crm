"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="staff"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # contacts
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("address", sa.String(500)),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(2), server_default="IN"),
        sa.Column("zip", sa.String(10)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # pipeline_stages
    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_closed_won", sa.Boolean(), server_default="false"),
        sa.Column("is_closed_lost", sa.Boolean(), server_default="false"),
    )

    # leads
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id")),
        sa.Column("stage_id", sa.Integer(), sa.ForeignKey("pipeline_stages.id")),
        sa.Column("source", sa.String(100)),
        sa.Column("description", sa.Text()),
        sa.Column(
            "assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # jobs
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id")),
        sa.Column("stage_id", sa.Integer(), sa.ForeignKey("pipeline_stages.id")),
        sa.Column(
            "assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id")
        ),
        sa.Column("job_type", sa.String(50)),
        sa.Column("work_type", sa.String(20)),
        sa.Column("property_address", sa.String(500)),
        sa.Column("notes", sa.Text()),
        sa.Column("contract_value", sa.Numeric(12, 2)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # estimates
    op.create_table(
        "estimates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id")),
        sa.Column("name", sa.String(255)),
        sa.Column("subtotal", sa.Numeric(12, 2)),
        sa.Column("tax", sa.Numeric(12, 2)),
        sa.Column("total", sa.Numeric(12, 2)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # estimate_line_items
    op.create_table(
        "estimate_line_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("estimate_id", sa.Integer(), sa.ForeignKey("estimates.id")),
        sa.Column("description", sa.String(500)),
        sa.Column("qty", sa.Numeric(12, 2)),
        sa.Column("unit_price", sa.Numeric(12, 2)),
        sa.Column("line_total", sa.Numeric(12, 2)),
        sa.Column("sort_order", sa.Integer()),
    )

    # tasks
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("due_date", sa.Date()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_table("estimate_line_items")
    op.drop_table("estimates")
    op.drop_table("jobs")
    op.drop_table("leads")
    op.drop_table("pipeline_stages")
    op.drop_table("contacts")
    op.drop_table("users")
