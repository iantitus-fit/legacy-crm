---
type: object
cluster: money
status: live
verified: 2026-10-01 · public copy of 7fbda4a + money-path fixes
entity: backend/app/models/invoice.py
---
# invoice

**Type:** object · **Mark:** live · **Checked:** 2026-10-01 · **Where:** backend/app/models/invoice.py:19

## One sentence
A bill to the homeowner: a deposit (one line, a percent of the estimate) or the final invoice (the estimate, plus approved change orders, less deposits already billed).

## Why this shape
The invoice must not move when someone edits the estimate later. So it owns copies of the items
(`invoice_items`, tagged by `source_type`: estimate / change_order / deposit / deposit_credit) and
recalculates on its own.

## Shape
- Number: `INV-` + one past the highest INV number on file (backend/app/routers/invoices.py:51). Imported AccuLynx numbers like `1004-1` are ignored by the sequence.
- Final: `POST /api/invoices` (backend/app/routers/invoices.py:168). Requires an approved estimate; one non-deposit invoice per estimate. See invoice-from-estimate.
- Deposit: `POST /api/invoices/deposit` (backend/app/routers/invoices.py:303). Allowed before approval, tax 0, single line; refused once a final invoice exists (:337).
- Totals: `_recalculate_invoice` (backend/app/routers/invoices.py:67). Tax applies to the work only; `deposit_credit` lines come off after tax (:83). NULL `tax_rate` falls back to 0.07 (:94).
- Credit lines carry `source_invoice_id` (backend/app/models/invoice_item.py:31, migration 0031). Voiding a deposit removes its credit from the final and re-derives that invoice's status (backend/app/routers/invoices.py:492).
- Status: draft at create, sent on email (:791), then derived from payments (see payment). `PUT` accepts only draft, sent, void (`MANUAL_STATUSES`, :48).
- `job_id` is required (see job).

## Connected to
- owned-by: job, estimate (optional FK)
- owns: invoice items, payments
- looks-like-but-is-not: the estimate's totals. Same items, separate math.

## If you change this
- **Hits:** invoice PDF (credits render under the totals, :674) and the invoice page, email, payments (balance and status), dashboard open-invoices, reports, the morning briefing's cash section.
- **Does not hit:** the estimate or its change orders. Nothing flows back.

## Surfaces
Invoice pages, client profile Invoices tab, dashboard, briefing, reports (exclude `void`).

## See
backend/app/routers/invoices.py
