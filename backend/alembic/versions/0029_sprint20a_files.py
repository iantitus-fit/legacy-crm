"""Sprint 20a: extend documents table for file/photo management.

Adds estimate_id polymorphic target plus folder/photo/visibility columns
so the existing documents table can back the new FilesTab UI. Keeps
job_id for legacy JobDetailPage back-compat (per CLAUDE.md rule 13 the
jobs table is deprecated, but its detail view is still in use).

The "at least one entity" CHECK constraint replaces the spec's "exactly
one" rule — Sprint 15a uploads dual-link contact+job, so a strict
constraint would fail to apply against production data. New uploads
attach to a single entity; existing dual-linked rows continue to work.

Revision ID: 0029
Revises: 0028
"""

from alembic import op
import sqlalchemy as sa


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(
            sa.Column("estimate_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "folder",
                sa.String(length=100),
                nullable=False,
                server_default="General",
            )
        )
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "is_photo",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "show_in_work_order",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "show_in_estimate",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column("uploaded_by", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch_op.create_foreign_key(
            "fk_documents_estimate_id",
            "estimates",
            ["estimate_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_documents_uploaded_by",
            "users",
            ["uploaded_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_documents_one_entity",
            "(contact_id IS NOT NULL) OR (job_id IS NOT NULL) "
            "OR (estimate_id IS NOT NULL)",
        )

    op.create_index(
        "ix_documents_estimate_id",
        "documents",
        ["estimate_id"],
    )
    op.create_index(
        "ix_documents_folder",
        "documents",
        ["folder"],
    )
    op.create_index(
        "ix_documents_is_photo",
        "documents",
        ["is_photo"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_is_photo", table_name="documents")
    op.drop_index("ix_documents_folder", table_name="documents")
    op.drop_index("ix_documents_estimate_id", table_name="documents")

    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("ck_documents_one_entity", type_="check")
        batch_op.drop_constraint("fk_documents_uploaded_by", type_="foreignkey")
        batch_op.drop_constraint("fk_documents_estimate_id", type_="foreignkey")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("uploaded_by")
        batch_op.drop_column("show_in_estimate")
        batch_op.drop_column("show_in_work_order")
        batch_op.drop_column("is_photo")
        batch_op.drop_column("description")
        batch_op.drop_column("folder")
        batch_op.drop_column("estimate_id")
