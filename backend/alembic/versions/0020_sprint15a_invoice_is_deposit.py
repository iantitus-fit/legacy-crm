"""Sprint 15a: invoices.is_deposit flag

Revision ID: 0020
Revises: 0019

Adds a boolean `is_deposit` column to invoices so deposit invoices can
coexist with a single final invoice per estimate. Existing rows
backfill to False.
"""

from alembic import op
import sqlalchemy as sa


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "invoices",
        sa.Column(
            "is_deposit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade():
    op.drop_column("invoices", "is_deposit")
