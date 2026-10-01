"""Change orders and change order items

Revision ID: 0013
Revises: 0012
"""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "change_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("estimate_id", sa.Integer(), sa.ForeignKey("estimates.id"), nullable=False),
        sa.Column("co_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), server_default="0"),
        sa.Column("tax", sa.Numeric(12, 2), server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "change_order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("change_order_id", sa.Integer(), sa.ForeignKey("change_orders.id"), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_table("change_order_items")
    op.drop_table("change_orders")
