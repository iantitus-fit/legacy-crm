---
type: object
cluster: money
status: live
verified: 2026-10-01 · public copy of 7fbda4a + money-path fixes
entity: backend/app/models/payment.py
---
# payment

**Type:** object · **Mark:** live · **Checked:** 2026-10-01 · **Where:** backend/app/routers/payments.py:120

## One sentence
Money received against one invoice: date, amount, method, reference.

## Why this shape
Status should never be set by hand once money moves. Every payment write re-derives the invoice's
`amount_paid`, `balance`, and status from the sum of its payments.

## Shape
- `record_payment` (backend/app/routers/payments.py:120): rejects void invoices and amounts <= 0, inserts, recalculates, optionally emails a receipt.
- `recalculate_invoice_payments` (backend/app/routers/payments.py:34): void stays void; balance <= 0 is paid; any amount paid is partial; otherwise sent if `date_invoiced` is set, else draft.
- Edit and delete also recalculate (backend/app/routers/payments.py:185, :219). So does voiding a deposit that a final invoice had credited.

## Connected to
- owned-by: invoice
- looks-like-but-is-not: a deposit invoice. `payment.is_deposit` is a label on money received; `invoice.is_deposit` is a whole invoice.

## If you change this
- **Hits:** invoice status and balance, receipts, dashboard and briefing cash figures.
- **Does not hit:** invoice line items or totals.

## Surfaces
Invoice detail page (record / edit / delete / send receipt), receipt email.

## See
backend/app/routers/payments.py
