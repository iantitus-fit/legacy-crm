# Money-path map: catalog

Scope: the nouns a cold reader must understand before changing how a job's
money moves: estimate, change order, invoice, payment. Load this file, then
ONE card. Never the whole objects/ folder. Statuses: live / leftover / ghost /
half-wired (see _meta/statuses.md). Checked 2026-10-01 against the public
copy, after the money-path fixes. VERIFICATION.md holds open deviations (none
today) and the record of the nine that were found and fixed.

## By task (start here; each lane names the card and the wrong neighbor)
"Totals on an estimate look wrong"                 → estimate (Totals). Not invoice: the invoice recalculates on its own copy.
"Change waste, margin, or how a template prices"   → estimate-template. Not material: price-list changes never reach a saved template.
"Re-import a supplier price list"                  → material. Not estimate-template: templates hold their own unit_cost snapshot.
"Change what happens when an estimate is approved" → approve (process). Not estimate Status: approval is one function both entry points call.
"Add a status or change who can move an estimate"  → estimate (Status). Not approve: approval is one transition, not the machine.
"Change-order math or tax looks off"               → change-order. It follows the estimate's tax rule; start there if both look off.
"Invoice contents, numbering, or deposits"         → invoice, then invoice-from-estimate. Not payment: payments never change line items.
"Recording a payment or why status went partial"   → payment. Not invoice: status after creation is derived from payments.
"Portal link, signature, expiry, or a 409 / 410"   → portal-link. Not estimate: the link is its own table per document.
"Is the jobs table dead? Can I drop it?"           → job. Stop: it is load-bearing for every estimate and invoice.

## Nouns
job               live        parent row every estimate and invoice hangs off  objects/record/job.md
estimate          live        proposal, then the job itself once approved; owns line items, sections, status  objects/record/estimate.md
estimate-template live        roofing price engine: measurement x conversion, waste, round up, margin  objects/pricing/estimate-template.md
material          live        supplier price-list rows (1,550, OCR-imported) the template picker reads  objects/pricing/material.md
portal-link       live        public token + canvas signature for estimates and change orders; optional expiry  objects/portal/portal-link.md
change-order      live        numbered add-on to an approved estimate with its own portal and signature  objects/money/change-order.md
invoice           live        deposit, or final = estimate + approved COs - billed deposits  objects/money/invoice.md
payment           live        money received; the only thing that moves invoice status after send  objects/money/payment.md

## Processes (verbs that earned a card: 3+ nouns or multiple call sites)
approve                live   one function, two entry points (customer portal, internal)  processes/approve.md
invoice-from-estimate  live   snapshot of estimate + approved COs + deposit credits into invoice_items  processes/invoice-from-estimate.md
(send, view, reject, request-changes are edges on estimate and change-order)

## Named, nothing flowing through (no card; one line each)
GET /api/pipelines/{id}/board (job board)   half-wired (no reachable caller)  see job
GET /api/pipeline/board (singular router)   half-wired (no caller in repo)    see job

## Collisions
job = the jobs table row (live parent), not an approved estimate, not the Jobs pipeline
price = Material.unit_price (supplier cost) vs template unit_cost (snapshot) vs line unit_price (sell)
total = estimate.total (no COs) vs grand_total (with approved COs) vs invoice.total (after deposit credits)
deposit = invoice.is_deposit (a whole invoice) vs a deposit_credit line on the final vs payment.is_deposit (a flag on money)
Full list: _meta/collisions.md
