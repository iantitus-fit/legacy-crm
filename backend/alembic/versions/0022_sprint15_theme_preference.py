"""Sprint 15: Add theme_preference to users

Revision ID: 0022
Revises: 0021
"""

from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "theme_preference",
            sa.String(10),
            nullable=False,
            server_default="dark",
        ),
    )


def downgrade():
    op.drop_column("users", "theme_preference")
