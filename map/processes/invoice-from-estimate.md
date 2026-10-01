---
type: process
status: live
verified: 2026-10-01 · public copy of 7fbda4a + money-path fixes
consumes: [objects/record/estimate.md, objects/money/change-order.md]
produces: [objects/money/invoice.md]
---
# invoice-from-estimate

**Type:** process · **Mark:** live · **Checked:** 2026-10-01 · **Where:** backend/app/routers/invoices.py:168

## One sentence
Freeze an approved estimate, its approved change orders, and credits for deposits already billed into a final invoice.

## Input → Movement → Output
Input: an approved estimate. Movement: copy every estimate line item, every item of every approved
change order in CO-number order, then one negative `deposit_credit` line per non-void deposit
invoice. Output: a draft invoice whose total is what is still owed.

## Why this shape
Copy, not reference: the bill a homeowner received must not change when the estimate is edited
next month. `source_type`, `source_co_number` and `source_invoice_id` keep each line's origin visible.
Deposits are post-tax dollars, so their credit comes off after tax.

## Steps
1. Load the estimate with line items, job, and change orders.
2. Refuse unless `status == approved` (backend/app/routers/invoices.py:188) and no other non-deposit invoice exists for it (:200).
3. Number it (:202, see invoice). Tax rate 0 when the estimate is `tax_included`, else the estimate's rate (:204).
4. Insert the invoice with `job_id = estimate.job_id` (:206).
5. Copy estimate items, then approved CO items (:223).
6. Add a credit line per deposit invoice for the estimate that is not void (:257).
7. `_recalculate_invoice` (:284; defined at :67).

## Hits / Does not hit
- **Hits:** invoice, invoice items, the invoice number sequence, open-invoice figures on the dashboard and in the briefing.
- **Does not hit:** the deposit invoices themselves (they stay as billed) or change orders approved later (not appended to an existing invoice).

## Surfaces
"Create invoice" on the estimate detail page; client profile Invoices tab.

## See
backend/app/routers/invoices.py
