"""Sprint 16a: CSV contact importer schema

Revision ID: 0024
Revises: 0023
"""
from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_imports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("field_mappings", sa.JSON(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.add_column(
        "contacts",
        sa.Column("import_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "contacts",
        sa.Column("import_source_file", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "contacts",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_contacts_import_id", "contacts", ["import_id"]
    )
    op.create_index(
        "ix_contacts_deleted_at", "contacts", ["deleted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_contacts_deleted_at", table_name="contacts")
    op.drop_index("ix_contacts_import_id", table_name="contacts")
    op.drop_column("contacts", "deleted_at")
    op.drop_column("contacts", "import_source_file")
    op.drop_column("contacts", "import_id")
    op.drop_table("contact_imports")
