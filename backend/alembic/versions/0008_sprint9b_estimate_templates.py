"""Sprint 9b: Estimate templates and template items.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "estimate_templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "default_margin_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="46.00",
        ),
        sa.Column(
            "default_waste_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="10.00",
        ),
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

    op.create_table(
        "estimate_template_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer,
            sa.ForeignKey("estimate_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "material_id",
            sa.Integer,
            sa.ForeignKey("materials.id"),
            nullable=True,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("uom", sa.String(20), nullable=True),
        sa.Column(
            "margin_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="46.00",
        ),
        sa.Column(
            "waste_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="10.00",
        ),
        sa.Column("measurement_type", sa.String(50), nullable=True),
        sa.Column(
            "conversion_factor",
            sa.Numeric(10, 4),
            nullable=False,
            server_default="1.0000",
        ),
        sa.Column("default_qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_template_items_template_id",
        "estimate_template_items",
        ["template_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_template_items_template_id", table_name="estimate_template_items")
    op.drop_table("estimate_template_items")
    op.drop_table("estimate_templates")
