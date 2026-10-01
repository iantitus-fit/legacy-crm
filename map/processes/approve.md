---
type: process
status: live
verified: 2026-10-01 · public copy of 7fbda4a + money-path fixes
consumes: [objects/record/estimate.md, objects/portal/portal-link.md]
produces: [objects/record/estimate.md, objects/record/job.md]
---
# approve

**Type:** process · **Mark:** live · **Checked:** 2026-10-01 · **Where:** backend/app/services/estimate_approval.py:33

## One sentence
An estimate becomes the job: status goes to `approved` and the work lands on the Jobs board as Pending Schedule.

## Input → Movement → Output
Input: an estimate in draft / sent / viewed. Movement: one function sets the approval fields, logs
history, and moves the estimate and its job row to Jobs / Pending Schedule. Output: an approved
estimate the invoice and change-order flows will accept.

## Why this shape
Most homeowners sign through the portal; some say yes on the phone, so the salesperson needs an
internal approve. Both used to carry their own copy of the logic and drifted apart (the portal path
never placed the estimate on the board). Now both call `approve_estimate`. PUT cannot approve
(backend/app/routers/estimates.py:407-415), so one of these two always runs.

## Steps
1. **Customer portal** `POST /api/portal/{token}/approve` (backend/app/routers/customer_portal.py:206): link must be live and the estimate open (portal-link), signer name, signature and terms required (:213-217), signature row saved, then `approve_estimate` (:232). Afterward: owner email and the `estimate_approved` AI event.
2. **Internal** `POST /api/estimates/{id}/approve-internal` (backend/app/routers/estimates.py:1052): draft / sent / viewed only (:1070), then `approve_estimate` (:1076).
3. `approve_estimate` sets status, `approved_at`, `approved_by`, writes history, then sets `pipeline_id` / `stage_id` on the estimate (backend/app/services/estimate_approval.py:71) and its job row (:76). A missing Jobs pipeline or stage logs a warning and leaves placement alone.

## Hits / Does not hit
- **Hits:** estimate status, approval fields and history, estimate and job pipeline/stage, Jobs board, dashboard Jobs counts.
- **Does not hit:** invoices or change orders. Approval creates neither; it only unlocks them.

## Surfaces
Homeowner (portal), salesperson (estimate detail page), owner (notification email), AI events.

## See
backend/app/services/estimate_approval.py
