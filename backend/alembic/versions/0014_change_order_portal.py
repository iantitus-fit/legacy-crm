"""Change order tokens and signatures for portal

Revision ID: 0014
Revises: 0013
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "change_order_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("change_order_id", sa.Integer(), sa.ForeignKey("change_orders.id"), nullable=False),
        sa.Column("token", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "change_order_signatures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("change_order_id", sa.Integer(), sa.ForeignKey("change_orders.id"), nullable=False),
        sa.Column("signer_name", sa.String(100), nullable=False),
        sa.Column("signature_data", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("terms_accepted", sa.Boolean(), default=False),
    )


def downgrade():
    op.drop_table("change_order_signatures")
    op.drop_table("change_order_tokens")
