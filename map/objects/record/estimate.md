---
type: object
cluster: record
status: live
verified: 2026-10-01 · public copy of 7fbda4a + money-path fixes
entity: backend/app/models/estimate.py
---
# estimate

**Type:** object · **Mark:** live · **Checked:** 2026-10-01 · **Where:** backend/app/models/estimate.py:22

## One sentence
The proposal a customer signs, and after approval the job itself: crew, schedule, and work type live here.

## Why this shape
The owner thinks in proposals, not jobs. Making the approved estimate *be* the job removed a copy step
and a second source of truth for scope and price (root CLAUDE.md rule 13).

## Shape
- Line items and sections: `estimate_line_items`, `estimate_sections` (relationships at backend/app/models/estimate.py:104, :107).
- **Totals** come from one function: `recalculate_estimate` (backend/app/services/estimate_calculator.py:18). Line total = qty x unit_price, rounded half-up. `tax_included` (painting) means tax 0 and total = subtotal (:43); otherwise tax = subtotal x `tax_rate`, default 0.0700 (backend/app/models/estimate.py:30).
- `grand_total` in API responses = `total` + approved change-order totals (backend/app/routers/estimates.py:138, :179). Computed, not stored.
- **Status** machine lives in `update_estimate` (backend/app/routers/estimates.py:371-430): draft, sent, viewed, approved, in_progress, complete, closed, rejected, changes_requested. PUT cannot approve (:407-415); job-phase states require an approved estimate first.
- Every transition writes `estimate_status_history` with who and IP.

## Connected to
- owned-by: job (`job_id`, required)
- owns: line items, sections, change orders, signatures, status history, portal tokens
- looks-like-but-is-not: invoice (the invoice holds a copy of the items, not a reference)

## If you change this
- **Hits:** estimate PDF and email, customer portal, change-order tax (reads `tax_rate` and `tax_included`), invoice creation (copies items, reads `tax_included`), Jobs board and calendar (filter on job-phase statuses: backend/app/routers/pipelines.py:36, calendar.py:30), dashboard, client profile.
- **Does not hit:** existing invoices. Editing an estimate after invoicing leaves the invoice as it was.
- Adding a status: update `VALID_ESTIMATE_STATUSES`, the two job-phase tuples above, `OPEN_FOR_RESPONSE` if customers can answer in it (backend/app/services/estimate_approval.py:27), and the client-profile grouping (frontend/src/pages/ContactDetailPage.jsx:167).

## Surfaces
Writers: estimates router, customer portal (viewed / approved / rejected / changes_requested), estimate email (sent, backend/app/routers/estimate_email.py:139), apply-template. Readers: boards, calendar, dashboard, briefing, reports, client profile.

## See
backend/app/routers/estimates.py
