"""Add notes column to estimate_line_items

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "estimate_line_items",
        sa.Column("notes", sa.String(500), nullable=True),
    )


def downgrade():
    op.drop_column("estimate_line_items", "notes")
