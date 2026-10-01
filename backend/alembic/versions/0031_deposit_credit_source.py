"""Invoice items can point at the invoice they credit.

A final invoice now carries one "deposit_credit" line per deposit invoice
already billed for the same estimate. source_invoice_id ties that line to the
deposit invoice so voiding the deposit can remove its credit.

Revision ID: 0031
Revises: 0030
"""

from alembic import op
import sqlalchemy as sa


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("invoice_items") as batch_op:
        batch_op.add_column(sa.Column("source_invoice_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_invoice_items_source_invoice_id",
            "invoices",
            ["source_invoice_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("invoice_items") as batch_op:
        batch_op.drop_constraint("fk_invoice_items_source_invoice_id", type_="foreignkey")
        batch_op.drop_column("source_invoice_id")
