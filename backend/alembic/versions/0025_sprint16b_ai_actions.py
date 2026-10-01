"""Sprint 16b: AI actions audit log + estimate scope_of_work

Revision ID: 0025
Revises: 0024
"""
from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_actions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False, index=True),
        sa.Column(
            "contact_id",
            sa.Integer(),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "estimate_id",
            sa.Integer(),
            sa.ForeignKey("estimates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("user_prompt", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="completed",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_ai_actions_contact_id", "ai_actions", ["contact_id"]
    )
    op.create_index(
        "ix_ai_actions_estimate_id", "ai_actions", ["estimate_id"]
    )

    op.add_column(
        "estimates",
        sa.Column("scope_of_work", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("estimates", "scope_of_work")
    op.drop_index("ix_ai_actions_estimate_id", table_name="ai_actions")
    op.drop_index("ix_ai_actions_contact_id", table_name="ai_actions")
    op.drop_table("ai_actions")
