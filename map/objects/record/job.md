---
type: object
cluster: record
status: live
verified: 2026-10-01 · public copy of 7fbda4a + money-path fixes
entity: backend/app/models/job.py
---
# job

**Type:** object · **Mark:** live · **Checked:** 2026-10-01 · **Where:** backend/app/models/job.py:23

## One sentence
A row in the `jobs` table: the parent record every estimate and every invoice must point at.

## Why this shape
The original model was job-centric (AccuLynx works that way). An April 2026 restructure moved
client data to `contacts` and job-phase fields onto `estimates`, but the foreign keys stayed. The
root CLAUDE.md now says so: job rows are required parents, and new job-phase fields go on estimates.

## Shape
- `estimates.job_id` is required at create: `POST /api/estimates` 400s without a Job (backend/app/routers/estimates.py:309-316).
- `invoices.job_id` is `NOT NULL` (backend/app/models/invoice.py:23); both invoice creators copy `estimate.job_id` (backend/app/routers/invoices.py:206, :357).
- Created by lead conversion (backend/app/routers/leads.py:197, :253) and by the AccuLynx importer (backend/scripts/import_acculynx_v2.py, phase 3). `POST /api/jobs` exists (backend/app/routers/jobs.py:224); no page calls it.
- Carries `pipeline_id` / `stage_id` / `contract_value`, read by the dashboard (backend/app/routers/dashboard.py:85, :190).

## Connected to
- owns: estimates, invoices, tasks, documents (backend/app/models/job.py:64-67)
- owned-by: contact (`contact_id`)
- looks-like-but-is-not: an approved estimate (the product calls that "the job"); the Jobs pipeline board (reads estimates, see estimate)

## If you change this
- **Hits:** estimate creation, both invoice creators, dashboard counts and pipeline value, the importer, lead conversion, approval (moves the job row with the estimate).
- **Does not hit:** the Jobs pipeline board. It reads `estimates.pipeline_id`, not `jobs.pipeline_id` (backend/app/routers/pipelines.py:305, frontend/src/pages/PipelineBoardPage.jsx:120).
- Dropping or nulling this table breaks every estimate and invoice. Retiring it is its own migration, not a cleanup.

## Surfaces
Writes: lead convert, importer, approval (backend/app/services/estimate_approval.py:76). Reads: dashboard, job detail page, `GET /api/pipelines/{id}/board` (only reached for pipeline slugs other than leads/sales/jobs). VERIFY: does production hold any pipeline besides the three seeded ones? · settles by: `SELECT slug FROM pipelines;` or the owner.

## See
backend/app/models/job.py
