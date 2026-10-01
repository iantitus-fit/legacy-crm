"""Sprint 5: multi-pipeline architecture

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New pipeline definitions with stages and colors
PIPELINES = [
    {
        "name": "Leads",
        "slug": "leads",
        "description": "Track incoming leads and inquiries",
        "display_order": 1,
        "stages": [
            {"name": "Cold Leads", "sort_order": 1, "color": "#3B82F6"},
            {"name": "Warm Leads", "sort_order": 2, "color": "#F59E0B"},
            {"name": "No Answer", "sort_order": 3, "color": "#6B7280"},
            {"name": "Angi Leads", "sort_order": 4, "color": "#10B981"},
            {"name": "Website Inquiry", "sort_order": 5, "color": "#8B5CF6"},
        ],
    },
    {
        "name": "Sales",
        "slug": "sales",
        "description": "Manage estimates and proposals",
        "display_order": 2,
        "stages": [
            {"name": "Draft", "sort_order": 1, "color": "#6B7280"},
            {"name": "Estimate Sent", "sort_order": 2, "color": "#3B82F6"},
            {"name": "Cold Proposals", "sort_order": 3, "color": "#93C5FD"},
            {"name": "Warm Proposals", "sort_order": 4, "color": "#F59E0B"},
            {"name": "Hot Proposals", "sort_order": 5, "color": "#EF4444"},
        ],
    },
    {
        "name": "Jobs",
        "slug": "jobs",
        "description": "Active jobs and scheduling",
        "display_order": 3,
        "stages": [
            {"name": "Pending Schedule", "sort_order": 1, "color": "#F59E0B"},
            {"name": "Scheduled", "sort_order": 2, "color": "#3B82F6"},
            {"name": "In Progress", "sort_order": 3, "color": "#10B981"},
            {"name": "Complete", "sort_order": 4, "color": "#22C55E"},
            {"name": "Warranty", "sort_order": 5, "color": "#8B5CF6"},
            {"name": "Closed", "sort_order": 6, "color": "#6B7280"},
        ],
    },
]

# Map old stage names to (pipeline_slug, new_stage_name)
OLD_TO_NEW = {
    "New Lead": ("leads", "Cold Leads"),
    "Inspection Scheduled": ("sales", "Draft"),
    "Estimate Sent": ("sales", "Estimate Sent"),
    "Negotiation": ("sales", "Warm Proposals"),
    "Closed Won": ("jobs", "Complete"),
    "Closed Lost": ("jobs", "Closed"),
}


def upgrade() -> None:
    # 1. Create pipelines table
    op.create_table(
        "pipelines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
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

    # 2. Add new columns to pipeline_stages (nullable initially)
    op.add_column(
        "pipeline_stages",
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey("pipelines.id"), nullable=True),
    )
    op.add_column(
        "pipeline_stages",
        sa.Column("color", sa.String(7), nullable=True),
    )

    # 3. Add new columns to jobs (nullable initially)
    op.add_column(
        "jobs",
        sa.Column("pipeline_id", sa.Integer(), sa.ForeignKey("pipelines.id"), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("lead_source", sa.String(100), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("display_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("labels", sa.JSON(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 4. Drop global unique constraint on name BEFORE inserting new stages
    #    (new stages like "Estimate Sent" collide with old ones under global unique)
    op.drop_constraint("pipeline_stages_name_key", "pipeline_stages", type_="unique")

    # 5. Data migration: insert pipelines and new stages, remap jobs
    conn = op.get_bind()

    # Insert pipelines
    pipelines_table = sa.table(
        "pipelines",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("description", sa.Text),
        sa.column("display_order", sa.Integer),
    )
    pipeline_id_map = {}  # slug -> id
    for p in PIPELINES:
        result = conn.execute(
            pipelines_table.insert()
            .values(
                name=p["name"],
                slug=p["slug"],
                description=p["description"],
                display_order=p["display_order"],
            )
            .returning(pipelines_table.c.id)
        )
        pipeline_id_map[p["slug"]] = result.scalar()

    # Insert new stages
    stages_table = sa.table(
        "pipeline_stages",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_closed_won", sa.Boolean),
        sa.column("is_closed_lost", sa.Boolean),
        sa.column("pipeline_id", sa.Integer),
        sa.column("color", sa.String),
    )
    new_stage_map = {}  # (pipeline_slug, stage_name) -> stage_id
    for p in PIPELINES:
        pid = pipeline_id_map[p["slug"]]
        for s in p["stages"]:
            result = conn.execute(
                stages_table.insert()
                .values(
                    name=s["name"],
                    sort_order=s["sort_order"],
                    is_closed_won=False,
                    is_closed_lost=False,
                    pipeline_id=pid,
                    color=s["color"],
                )
                .returning(stages_table.c.id)
            )
            new_stage_map[(p["slug"], s["name"])] = result.scalar()

    # Read old stages
    old_rows = conn.execute(
        sa.text("SELECT id, name FROM pipeline_stages WHERE pipeline_id IS NULL")
    ).fetchall()
    old_stage_map = {name: sid for sid, name in old_rows}

    # Remap jobs from old stages to new stages
    for old_name, (pipeline_slug, new_name) in OLD_TO_NEW.items():
        old_id = old_stage_map.get(old_name)
        if old_id is None:
            continue
        new_stage_id = new_stage_map[(pipeline_slug, new_name)]
        new_pipeline_id = pipeline_id_map[pipeline_slug]
        conn.execute(
            sa.text(
                "UPDATE jobs SET stage_id = :new_stage, pipeline_id = :new_pipeline "
                "WHERE stage_id = :old_stage"
            ),
            {"new_stage": new_stage_id, "new_pipeline": new_pipeline_id, "old_stage": old_id},
        )

    # Jobs with no stage or unmapped stage: assign to Leads pipeline / Cold Leads
    default_pipeline_id = pipeline_id_map["leads"]
    default_stage_id = new_stage_map[("leads", "Cold Leads")]
    conn.execute(
        sa.text(
            "UPDATE jobs SET pipeline_id = :pid, stage_id = :sid "
            "WHERE pipeline_id IS NULL"
        ),
        {"pid": default_pipeline_id, "sid": default_stage_id},
    )

    # Remap leads' stage_id to the first Leads pipeline stage
    conn.execute(
        sa.text("UPDATE leads SET stage_id = :sid WHERE stage_id IS NOT NULL"),
        {"sid": default_stage_id},
    )

    # Delete old stages (the ones without pipeline_id)
    conn.execute(
        sa.text("DELETE FROM pipeline_stages WHERE pipeline_id IS NULL")
    )

    # 6. Add composite unique constraint (pipeline_id, name)
    op.create_unique_constraint(
        "uq_pipeline_stage_name", "pipeline_stages", ["pipeline_id", "name"]
    )

    # 7. Make pipeline_id NOT NULL now that data is migrated
    op.alter_column("pipeline_stages", "pipeline_id", nullable=False)
    op.alter_column("jobs", "pipeline_id", nullable=False)


def downgrade() -> None:
    # Make pipeline_id nullable again
    op.alter_column("jobs", "pipeline_id", nullable=True)
    op.alter_column("pipeline_stages", "pipeline_id", nullable=True)

    # Restore global unique on name
    op.drop_constraint("uq_pipeline_stage_name", "pipeline_stages", type_="unique")
    op.create_unique_constraint("pipeline_stages_name_key", "pipeline_stages", ["name"])

    # Drop new columns from jobs
    op.drop_column("jobs", "last_activity_at")
    op.drop_column("jobs", "labels")
    op.drop_column("jobs", "display_name")
    op.drop_column("jobs", "lead_source")
    op.drop_column("jobs", "pipeline_id")

    # Drop new columns from pipeline_stages
    op.drop_column("pipeline_stages", "color")
    op.drop_column("pipeline_stages", "pipeline_id")

    # Drop pipelines table
    op.drop_table("pipelines")
