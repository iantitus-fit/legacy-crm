"""Customer portal: estimate status, tokens, status history, signatures

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    # Add status column to estimates
    op.add_column(
        "estimates",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
    )

    # Create estimate_tokens table
    op.create_table(
        "estimate_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "estimate_id",
            sa.Integer(),
            sa.ForeignKey("estimates.id"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    # Create estimate_status_history table
    op.create_table(
        "estimate_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "estimate_id",
            sa.Integer(),
            sa.ForeignKey("estimates.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("changed_by_name", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    # Create estimate_signatures table
    op.create_table(
        "estimate_signatures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "estimate_id",
            sa.Integer(),
            sa.ForeignKey("estimates.id"),
            nullable=False,
        ),
        sa.Column("signer_name", sa.String(100), nullable=False),
        sa.Column("signature_data", sa.Text(), nullable=False),
        sa.Column(
            "signed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("terms_accepted", sa.Boolean(), default=False),
    )


def downgrade():
    op.drop_table("estimate_signatures")
    op.drop_table("estimate_status_history")
    op.drop_table("estimate_tokens")
    op.drop_column("estimates", "status")
