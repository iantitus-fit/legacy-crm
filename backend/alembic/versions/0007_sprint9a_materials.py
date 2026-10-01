"""Sprint 9a: Materials database — price lists and materials library.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_lists",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("source_file", sa.String(255), nullable=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("expiration_date", sa.Date, nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "imported_by_user_id",
            sa.Integer,
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    op.create_table(
        "materials",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "price_list_id",
            sa.Integer,
            sa.ForeignKey("price_lists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_number", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("uom", sa.String(10), nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("ocr_flag", sa.String(200), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
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
    op.create_index(
        "ix_materials_price_list_item",
        "materials",
        ["price_list_id", "item_number"],
    )
    op.create_index(
        "ix_materials_category",
        "materials",
        ["category"],
    )


def downgrade() -> None:
    op.drop_index("ix_materials_category", table_name="materials")
    op.drop_index("ix_materials_price_list_item", table_name="materials")
    op.drop_table("materials")
    op.drop_table("price_lists")
