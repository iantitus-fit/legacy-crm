"""Sprint 7: Calendars — job scheduling + appointments.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Extend jobs table with scheduling fields --
    op.add_column("jobs", sa.Column("scheduled_date", sa.Date(), nullable=True))
    op.add_column("jobs", sa.Column("scheduled_end_date", sa.Date(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "crew_id",
            sa.Integer(),
            sa.ForeignKey("crews.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # -- New appointments table --
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "contact_id",
            sa.Integer(),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_to_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("appointment_time", sa.Time(), nullable=True),
        sa.Column(
            "duration_minutes", sa.Integer(), nullable=False, server_default="60"
        ),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "appointment_type",
            sa.String(20),
            nullable=False,
            server_default="other",
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
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


def downgrade() -> None:
    op.drop_table("appointments")
    op.drop_column("jobs", "crew_id")
    op.drop_column("jobs", "scheduled_end_date")
    op.drop_column("jobs", "scheduled_date")
