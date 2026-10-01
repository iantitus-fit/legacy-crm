"""Sprint 15a: documents.job_id becomes nullable

Revision ID: 0021
Revises: 0020

Contact-centric uploads can target a contact directly without a
preexisting job, so documents.job_id must accept NULL. Existing rows
are unaffected — all current documents are linked to a job.
"""

from alembic import op
import sqlalchemy as sa


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column("job_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column("job_id", existing_type=sa.Integer(), nullable=False)
