"""Sprint 15a: Backfill contacts/estimates/documents from jobs

Revision ID: 0019
Revises: 0018

Copies data from the jobs table onto contacts, estimates, and documents
so the new model has values to work with. Non-destructive: no rows are
deleted, no columns are dropped, and the jobs table is left intact.

Rules:
  - contacts.lead_source / pipeline_id / stage_id: copied from each
    contact's most-recent job (by created_at DESC). client_type defaults
    to 'residential'.
  - estimates.job_type / work_type / location_address / assigned_to_user_id
    / crew_id / scheduled_start / scheduled_end / pipeline_id / stage_id:
    copied from the estimate's parent job. approved_at set to NOW() when
    the estimate is currently in status 'approved' and approved_at is
    still NULL (best-effort fallback — actual approval timestamp was
    never recorded).
  - documents.contact_id: copied from the document's job.contact_id.
  - Skip placeholder creation: jobs without estimates stay as jobs; their
    lead_source etc. still get copied up to the contact, so the contact
    is ready for the new Client Profile UI.

Idempotency:
  - Every UPDATE guards with 'IS NULL' so re-running is a no-op on
    already-backfilled rows.
  - Safe to run on a database that's already been partially migrated.

Downgrade:
  - Clears the fields this migration populated. Because the fields were
    NULL before migration 0018, setting them back to NULL restores the
    pre-migration state.
"""

from alembic import op


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # --- contacts: copy lead_source / pipeline_id / stage_id from most
    # --- recent job, default client_type to 'residential'.
    if dialect == "postgresql":
        bind.exec_driver_sql(
            """
            UPDATE contacts c
            SET
              lead_source = COALESCE(c.lead_source, j.lead_source),
              pipeline_id = COALESCE(c.pipeline_id, j.pipeline_id),
              stage_id    = COALESCE(c.stage_id, j.stage_id)
            FROM (
              SELECT DISTINCT ON (contact_id)
                contact_id, lead_source, pipeline_id, stage_id
              FROM jobs
              WHERE contact_id IS NOT NULL
              ORDER BY contact_id, created_at DESC
            ) j
            WHERE c.id = j.contact_id
              AND (c.lead_source IS NULL OR c.pipeline_id IS NULL OR c.stage_id IS NULL);
            """
        )
    else:
        # SQLite (test DB) doesn't support DISTINCT ON or UPDATE...FROM.
        # Fall back to a correlated subquery pattern.
        bind.exec_driver_sql(
            """
            UPDATE contacts
            SET
              lead_source = COALESCE(
                lead_source,
                (SELECT lead_source FROM jobs
                 WHERE jobs.contact_id = contacts.id
                 ORDER BY jobs.created_at DESC LIMIT 1)
              ),
              pipeline_id = COALESCE(
                pipeline_id,
                (SELECT pipeline_id FROM jobs
                 WHERE jobs.contact_id = contacts.id
                 ORDER BY jobs.created_at DESC LIMIT 1)
              ),
              stage_id = COALESCE(
                stage_id,
                (SELECT stage_id FROM jobs
                 WHERE jobs.contact_id = contacts.id
                 ORDER BY jobs.created_at DESC LIMIT 1)
              );
            """
        )

    bind.exec_driver_sql(
        """
        UPDATE contacts
        SET client_type = 'residential'
        WHERE client_type IS NULL;
        """
    )

    # --- estimates: copy job-phase fields from parent job.
    if dialect == "postgresql":
        bind.exec_driver_sql(
            """
            UPDATE estimates e
            SET
              job_type             = COALESCE(e.job_type, j.job_type),
              work_type            = COALESCE(e.work_type, j.work_type),
              location_address     = COALESCE(e.location_address, j.property_address),
              crew_id              = COALESCE(e.crew_id, j.crew_id),
              scheduled_start      = COALESCE(e.scheduled_start, j.scheduled_date),
              scheduled_end        = COALESCE(e.scheduled_end, j.scheduled_end_date),
              assigned_to_user_id  = COALESCE(e.assigned_to_user_id, j.assigned_to_user_id),
              pipeline_id          = COALESCE(e.pipeline_id, j.pipeline_id),
              stage_id             = COALESCE(e.stage_id, j.stage_id)
            FROM jobs j
            WHERE e.job_id = j.id;
            """
        )
    else:
        bind.exec_driver_sql(
            """
            UPDATE estimates
            SET
              job_type = COALESCE(
                job_type,
                (SELECT job_type FROM jobs WHERE jobs.id = estimates.job_id)
              ),
              work_type = COALESCE(
                work_type,
                (SELECT work_type FROM jobs WHERE jobs.id = estimates.job_id)
              ),
              location_address = COALESCE(
                location_address,
                (SELECT property_address FROM jobs WHERE jobs.id = estimates.job_id)
              ),
              crew_id = COALESCE(
                crew_id,
                (SELECT crew_id FROM jobs WHERE jobs.id = estimates.job_id)
              ),
              scheduled_start = COALESCE(
                scheduled_start,
                (SELECT scheduled_date FROM jobs WHERE jobs.id = estimates.job_id)
              ),
              scheduled_end = COALESCE(
                scheduled_end,
                (SELECT scheduled_end_date FROM jobs WHERE jobs.id = estimates.job_id)
              ),
              assigned_to_user_id = COALESCE(
                assigned_to_user_id,
                (SELECT assigned_to_user_id FROM jobs WHERE jobs.id = estimates.job_id)
              ),
              pipeline_id = COALESCE(
                pipeline_id,
                (SELECT pipeline_id FROM jobs WHERE jobs.id = estimates.job_id)
              ),
              stage_id = COALESCE(
                stage_id,
                (SELECT stage_id FROM jobs WHERE jobs.id = estimates.job_id)
              )
            WHERE job_id IS NOT NULL;
            """
        )

    # --- estimates.approved_at fallback for already-approved estimates.
    # NOW() is a reasonable stand-in since the real approval time was
    # never recorded. approved_by stays NULL (we don't know whether it
    # was portal or internal).
    if dialect == "postgresql":
        bind.exec_driver_sql(
            """
            UPDATE estimates
            SET approved_at = NOW()
            WHERE status = 'approved' AND approved_at IS NULL;
            """
        )
    else:
        bind.exec_driver_sql(
            """
            UPDATE estimates
            SET approved_at = CURRENT_TIMESTAMP
            WHERE status = 'approved' AND approved_at IS NULL;
            """
        )

    # --- documents: copy contact_id from the document's job.
    if dialect == "postgresql":
        bind.exec_driver_sql(
            """
            UPDATE documents d
            SET contact_id = j.contact_id
            FROM jobs j
            WHERE d.job_id = j.id
              AND d.contact_id IS NULL
              AND j.contact_id IS NOT NULL;
            """
        )
    else:
        bind.exec_driver_sql(
            """
            UPDATE documents
            SET contact_id = (
              SELECT contact_id FROM jobs WHERE jobs.id = documents.job_id
            )
            WHERE contact_id IS NULL
              AND EXISTS (
                SELECT 1 FROM jobs
                WHERE jobs.id = documents.job_id
                  AND jobs.contact_id IS NOT NULL
              );
            """
        )


def downgrade():
    bind = op.get_bind()
    # Reverse the backfill by clearing the columns this migration wrote.
    # The pre-0018 state had these columns absent; setting them to NULL
    # returns the database to the shape expected by migration 0018.
    bind.exec_driver_sql(
        """
        UPDATE contacts
        SET lead_source = NULL,
            client_type = NULL,
            pipeline_id = NULL,
            stage_id    = NULL;
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE estimates
        SET job_type            = NULL,
            work_type           = NULL,
            location_address    = NULL,
            crew_id             = NULL,
            scheduled_start     = NULL,
            scheduled_end       = NULL,
            assigned_to_user_id = NULL,
            approved_at         = NULL,
            approved_by         = NULL,
            pipeline_id         = NULL,
            stage_id            = NULL;
        """
    )
    bind.exec_driver_sql("UPDATE documents SET contact_id = NULL;")
