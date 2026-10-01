"""Sprint 15a: Additive restructure columns for Client Profile + Estimate-is-Job

Revision ID: 0018
Revises: 0017

Adds columns to contacts and estimates to support the data model
restructure. This migration is purely additive — all new columns are
nullable and existing code continues to work unchanged. Data backfill
happens in migration 0019.

New on contacts:
  - lead_source (VARCHAR 100)        -- moved from jobs
  - client_type (VARCHAR 20)         -- 'residential' | 'commercial'
  - pipeline_id (INT, FK pipelines)  -- contact-level pipeline tracking
  - stage_id (INT, FK pipeline_stages)

New on estimates:
  - job_type (VARCHAR 50)            -- roof, gutters, siding, painting, etc.
  - work_type (VARCHAR 20)           -- 'retail' | 'insurance'
  - location_address (TEXT)          -- estimate-specific address
  - crew_id (INT, FK crews)
  - scheduled_start (DATE)
  - scheduled_end (DATE)
  - assigned_to_user_id (INT, FK users)
  - approved_at (TIMESTAMP)
  - approved_by (VARCHAR 100)        -- 'customer_portal' | 'internal' | customer name
  - pipeline_id (INT, FK pipelines)  -- estimate-level pipeline tracking (for Jobs Pipeline)
  - stage_id (INT, FK pipeline_stages)

New on documents:
  - contact_id (INT, FK contacts)    -- dual-link alongside existing job_id
"""

from alembic import op
import sqlalchemy as sa


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    # contacts -- client profile fields
    op.add_column("contacts", sa.Column("lead_source", sa.String(100), nullable=True))
    op.add_column("contacts", sa.Column("client_type", sa.String(20), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey("pipelines.id"), nullable=True),
    )
    op.add_column(
        "contacts",
        sa.Column("stage_id", sa.Integer(), sa.ForeignKey("pipeline_stages.id"), nullable=True),
    )

    # estimates -- job-phase fields
    op.add_column("estimates", sa.Column("job_type", sa.String(50), nullable=True))
    op.add_column("estimates", sa.Column("work_type", sa.String(20), nullable=True))
    op.add_column("estimates", sa.Column("location_address", sa.Text(), nullable=True))
    op.add_column(
        "estimates",
        sa.Column(
            "crew_id",
            sa.Integer(),
            sa.ForeignKey("crews.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("estimates", sa.Column("scheduled_start", sa.Date(), nullable=True))
    op.add_column("estimates", sa.Column("scheduled_end", sa.Date(), nullable=True))
    op.add_column(
        "estimates",
        sa.Column(
            "assigned_to_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column("estimates", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("estimates", sa.Column("approved_by", sa.String(100), nullable=True))
    op.add_column(
        "estimates",
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey("pipelines.id"), nullable=True),
    )
    op.add_column(
        "estimates",
        sa.Column(
            "stage_id",
            sa.Integer(),
            sa.ForeignKey("pipeline_stages.id"),
            nullable=True,
        ),
    )

    # documents -- dual-link to contact during transition
    op.add_column(
        "documents",
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=True),
    )


def downgrade():
    op.drop_column("documents", "contact_id")

    op.drop_column("estimates", "stage_id")
    op.drop_column("estimates", "pipeline_id")
    op.drop_column("estimates", "approved_by")
    op.drop_column("estimates", "approved_at")
    op.drop_column("estimates", "assigned_to_user_id")
    op.drop_column("estimates", "scheduled_end")
    op.drop_column("estimates", "scheduled_start")
    op.drop_column("estimates", "crew_id")
    op.drop_column("estimates", "location_address")
    op.drop_column("estimates", "work_type")
    op.drop_column("estimates", "job_type")

    op.drop_column("contacts", "stage_id")
    op.drop_column("contacts", "pipeline_id")
    op.drop_column("contacts", "client_type")
    op.drop_column("contacts", "lead_source")
