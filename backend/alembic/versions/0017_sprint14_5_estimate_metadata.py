"""Sprint 14.5: Add estimate expiration_date and created_by, contact company

Revision ID: 0017
Revises: 0016
"""

from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "estimates",
        sa.Column("expiration_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "estimates",
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "contacts",
        sa.Column("company", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("contacts", "company")
    op.drop_column("estimates", "created_by_user_id")
    op.drop_column("estimates", "expiration_date")
