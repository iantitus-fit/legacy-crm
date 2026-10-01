"""Sprint 19a: pipeline automations + drip sequences.

Adds four automation tables — sequences, steps, enrollments, logs — plus a
per-contact ``automations_enabled`` toggle. JSON column type is portable
across PostgreSQL (stored as JSONB-ish jsonb fallback isn't needed at this
volume) and SQLite (used in the test harness).

Revision ID: 0028
Revises: 0027
"""
from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # automation_sequences --------------------------------------------------
    op.create_table(
        "automation_sequences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column(
            "trigger_config",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            default=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_automation_sequences_trigger_type",
        "automation_sequences",
        ["trigger_type"],
    )
    op.create_index(
        "ix_automation_sequences_is_active",
        "automation_sequences",
        ["is_active"],
    )

    # automation_steps ------------------------------------------------------
    op.create_table(
        "automation_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "sequence_id",
            sa.Integer(),
            sa.ForeignKey("automation_sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column(
            "delay_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            default=0,
        ),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("template_subject", sa.String(length=255), nullable=True),
        sa.Column(
            "stop_on_reply",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            default=True,
        ),
        sa.Column(
            "stop_on_stage_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            default=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            default=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "sequence_id", "step_order", name="uq_automation_steps_seq_order"
        ),
    )
    op.create_index(
        "ix_automation_steps_sequence_id",
        "automation_steps",
        ["sequence_id"],
    )

    # automation_enrollments ------------------------------------------------
    op.create_table(
        "automation_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "sequence_id",
            sa.Integer(),
            sa.ForeignKey("automation_sequences.id"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            sa.Integer(),
            sa.ForeignKey("contacts.id"),
            nullable=False,
        ),
        sa.Column(
            "current_step_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            default=1,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
            default="active",
        ),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_reason", sa.Text(), nullable=True),
        sa.Column("next_step_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "sequence_id",
            "contact_id",
            name="uq_automation_enrollments_seq_contact",
        ),
    )
    op.create_index(
        "ix_automation_enrollments_status",
        "automation_enrollments",
        ["status"],
    )
    op.create_index(
        "ix_automation_enrollments_next_step_at",
        "automation_enrollments",
        ["next_step_at"],
    )
    op.create_index(
        "ix_automation_enrollments_contact_id",
        "automation_enrollments",
        ["contact_id"],
    )

    # automation_logs -------------------------------------------------------
    op.create_table(
        "automation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "enrollment_id",
            sa.Integer(),
            sa.ForeignKey("automation_enrollments.id"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            sa.Integer(),
            sa.ForeignKey("automation_steps.id"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("rendered_body", sa.Text(), nullable=False),
        sa.Column("rendered_subject", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
            default="pending",
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_automation_logs_enrollment_id",
        "automation_logs",
        ["enrollment_id"],
    )
    op.create_index(
        "ix_automation_logs_status", "automation_logs", ["status"]
    )
    op.create_index(
        "ix_automation_logs_created_at", "automation_logs", ["created_at"]
    )

    # contacts.automations_enabled ------------------------------------------
    op.add_column(
        "contacts",
        sa.Column(
            "automations_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            default=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("contacts", "automations_enabled")
    op.drop_index("ix_automation_logs_created_at", table_name="automation_logs")
    op.drop_index("ix_automation_logs_status", table_name="automation_logs")
    op.drop_index(
        "ix_automation_logs_enrollment_id", table_name="automation_logs"
    )
    op.drop_table("automation_logs")
    op.drop_index(
        "ix_automation_enrollments_contact_id",
        table_name="automation_enrollments",
    )
    op.drop_index(
        "ix_automation_enrollments_next_step_at",
        table_name="automation_enrollments",
    )
    op.drop_index(
        "ix_automation_enrollments_status", table_name="automation_enrollments"
    )
    op.drop_table("automation_enrollments")
    op.drop_index(
        "ix_automation_steps_sequence_id", table_name="automation_steps"
    )
    op.drop_table("automation_steps")
    op.drop_index(
        "ix_automation_sequences_is_active",
        table_name="automation_sequences",
    )
    op.drop_index(
        "ix_automation_sequences_trigger_type",
        table_name="automation_sequences",
    )
    op.drop_table("automation_sequences")
