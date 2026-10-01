# Collisions

One name, two meanings, inside the money path. Each line says which meaning is live where.

- **job.** (1) a row in `jobs`, the required parent of estimates and invoices (objects/record/job.md). (2) an approved estimate, which the product calls "the job". (3) the Jobs pipeline, whose board shows estimates, not job rows. Dashboard counts use (1); the board uses (2). Approval moves both.
- **price / cost.** `materials.unit_price` is supplier cost. `estimate_template_items.unit_cost` is a snapshot of that cost. `estimate_line_items.unit_price` is the sell price after waste and margin.
- **approved.** One estimate status, one function that sets it (backend/app/services/estimate_approval.py), two doors in: the customer portal (with a signature) and approve-internal (without one).
- **total.** `estimates.total` excludes change orders. `grand_total` (API only) adds approved change orders. `invoices.total` is recalculated from the invoice's own items and is net of deposit credits on a final invoice.
- **tax.** Estimates and change orders share one rule: `tax_included` means no separate tax, an explicit 0% stays 0%. A NULL rate falls back to 7% on change orders and invoices, and to 0 in the estimate calculator (the model defaults new estimates to 0.07, so NULL only appears if set on purpose).
- **deposit.** `invoices.is_deposit` is a whole invoice for a percent of the estimate. A `deposit_credit` line is that invoice's total taken back off the final. `payments.is_deposit` is a flag on money received.
- **sent.** Estimate status after the portal email (estimate_email.py:139). Change-order status after its email (change_orders.py:445). Invoice status after its email (invoices.py:791), and also the status payments recalc falls back to when `date_invoiced` is set.
- **closed (portal).** To a customer, anything not draft / sent / viewed is closed for answers; the portal pages show job-phase estimates as approved.
