"""Sprint 20b: work orders — number column + tokens table.

A work order is a rendered view of an existing estimate, so no new
"work_orders" table — just:

1. ``estimates.work_order_number`` — stamped on first WO generation
   as ``WO-{estimate.id}`` and reused thereafter.
2. ``work_order_tokens`` — public-link tokens, one per
   (estimate × is_secret) so the redaction flavor is bound to the
   token (no ``?secret=`` query that subs could flip).

Revision ID: 0030
Revises: 0029
"""

from alembic import op
import sqlalchemy as sa


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("estimates") as batch_op:
        batch_op.add_column(
            sa.Column("work_order_number", sa.String(length=50), nullable=True)
        )

    op.create_table(
        "work_order_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "estimate_id",
            sa.Integer(),
            sa.ForeignKey("estimates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "token", sa.String(length=64), nullable=False, unique=True
        ),
        sa.Column(
            "is_secret",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "estimate_id", "is_secret", name="uq_wo_token_estimate_secret"
        ),
    )
    op.create_index(
        "ix_work_order_tokens_token",
        "work_order_tokens",
        ["token"],
        unique=True,
    )
    op.create_index(
        "ix_work_order_tokens_estimate_id",
        "work_order_tokens",
        ["estimate_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_work_order_tokens_estimate_id", table_name="work_order_tokens")
    op.drop_index("ix_work_order_tokens_token", table_name="work_order_tokens")
    op.drop_table("work_order_tokens")
    with op.batch_alter_table("estimates") as batch_op:
        batch_op.drop_column("work_order_number")
