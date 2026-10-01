"""Sprint 17a: SMS messaging — sms_messages, sms_config, contacts.sms_opt_out

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "contact_id",
            sa.Integer(),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("from_number", sa.String(length=20), nullable=False),
        sa.Column("to_number", sa.String(length=20), nullable=False),
        sa.Column("twilio_sid", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("status_detail", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(length=30), nullable=True),
        sa.Column(
            "sent_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
        "ix_sms_messages_contact_id", "sms_messages", ["contact_id"]
    )
    op.create_index(
        "ix_sms_messages_created_at", "sms_messages", ["created_at"]
    )
    op.create_index(
        "ix_sms_messages_direction", "sms_messages", ["direction"]
    )
    op.create_index(
        "ix_sms_messages_twilio_sid", "sms_messages", ["twilio_sid"]
    )

    op.create_table(
        "sms_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("twilio_account_sid", sa.String(length=64), nullable=True),
        sa.Column(
            "twilio_auth_token_encrypted",
            sa.String(length=256),
            nullable=True,
        ),
        sa.Column("twilio_phone_number", sa.String(length=20), nullable=True),
        sa.Column(
            "auto_respond_new_lead",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            default=True,
        ),
        sa.Column(
            "auto_respond_after_hours",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            default=True,
        ),
        sa.Column(
            "business_hours_start",
            sa.Time(),
            nullable=False,
            server_default=sa.text("'08:00'"),
        ),
        sa.Column(
            "business_hours_end",
            sa.Time(),
            nullable=False,
            server_default=sa.text("'18:00'"),
        ),
        sa.Column(
            "business_timezone",
            sa.String(length=50),
            nullable=False,
            server_default="America/Indiana/Indianapolis",
        ),
        sa.Column(
            "new_lead_template",
            sa.Text(),
            nullable=False,
            server_default=(
                "Hi {first_name}, this is Legacy Roofing & Exteriors. "
                "We received your request and will be in touch shortly. "
                "Reply STOP to opt out."
            ),
        ),
        sa.Column(
            "after_hours_template",
            sa.Text(),
            nullable=False,
            server_default=(
                "Hi {first_name}, thanks for reaching out to Legacy "
                "Roofing & Exteriors. We're closed for the day but will "
                "call you first thing in the morning. Reply STOP to opt out."
            ),
        ),
        sa.Column(
            "estimate_sent_template",
            sa.Text(),
            nullable=False,
            server_default=(
                "Hi {first_name}, your estimate from Legacy Roofing is "
                "ready! View it here: {estimate_url} Reply STOP to opt out."
            ),
        ),
        sa.Column(
            "opt_out_keywords",
            sa.Text(),
            nullable=False,
            server_default="STOP,UNSUBSCRIBE,CANCEL,END,QUIT",
        ),
        sa.Column(
            "opt_in_keywords",
            sa.Text(),
            nullable=False,
            server_default="START,YES,UNSTOP",
        ),
        sa.Column(
            "help_response",
            sa.Text(),
            nullable=False,
            server_default=(
                "Legacy Roofing & Exteriors. Call us at (765) 555-0100 "
                "or visit legacy-roofing.example. Reply STOP to opt out."
            ),
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

    op.add_column(
        "contacts",
        sa.Column(
            "sms_opt_out",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            default=False,
        ),
    )
    op.add_column(
        "contacts",
        sa.Column("sms_opt_out_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contacts", "sms_opt_out_at")
    op.drop_column("contacts", "sms_opt_out")
    op.drop_table("sms_config")
    op.drop_index("ix_sms_messages_twilio_sid", table_name="sms_messages")
    op.drop_index("ix_sms_messages_direction", table_name="sms_messages")
    op.drop_index("ix_sms_messages_created_at", table_name="sms_messages")
    op.drop_index("ix_sms_messages_contact_id", table_name="sms_messages")
    op.drop_table("sms_messages")
