"""Sprint 10a: Add body to line items, display settings to estimates

Revision ID: 0010
Revises: 0009
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    # Rich text body for line items
    op.add_column(
        "estimate_line_items",
        sa.Column("body", sa.Text(), nullable=True),
    )

    # Display settings for estimates
    op.add_column(
        "estimates",
        sa.Column(
            "show_quantities",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "estimates",
        sa.Column(
            "show_unit_prices",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "estimates",
        sa.Column(
            "show_line_totals",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "estimates",
        sa.Column(
            "show_subtotal",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "estimates",
        sa.Column("deposit_percent", sa.Numeric(5, 2), nullable=True),
    )


def downgrade():
    op.drop_column("estimate_line_items", "body")
    op.drop_column("estimates", "show_quantities")
    op.drop_column("estimates", "show_unit_prices")
    op.drop_column("estimates", "show_line_totals")
    op.drop_column("estimates", "show_subtotal")
    op.drop_column("estimates", "deposit_percent")
