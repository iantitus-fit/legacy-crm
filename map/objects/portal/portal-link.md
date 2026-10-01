---
type: object
cluster: portal
status: live
verified: 2026-10-01 · public copy of 7fbda4a + money-path fixes
entity: backend/app/models/estimate_token.py
---
# portal-link

**Type:** object · **Mark:** live · **Checked:** 2026-10-01 · **Where:** backend/app/routers/customer_portal.py:34

## One sentence
A no-login link a homeowner opens to view, sign, reject, or ask for changes, plus the signature it captures.

## Why this shape
Customers will not create accounts. The token in the URL is the whole authorization, so each
document type gets its own token table and its own public router.

## Shape
- Estimates: `estimate_tokens` (minted at send, backend/app/routers/estimate_email.py:133), `estimate_signatures` (name, base64 canvas image, IP, terms accepted).
- Change orders: `change_order_tokens` (minted at send, backend/app/routers/change_orders.py:443), `change_order_signatures`.
- Work orders: `work_order_tokens` with an `is_secret` flag. Crew-facing, no pricing; the secret variant also redacts customer details (backend/app/services/work_order_pdf.py:4, :108).
- **Answer window:** approve / reject / request-changes only work while the document is draft, sent or viewed (`OPEN_FOR_RESPONSE`, backend/app/services/estimate_approval.py:27). Otherwise 409 (backend/app/routers/customer_portal.py:44, change_order_portal.py:34). A resend reopens it.
- **Expiry:** off by default. Set `PORTAL_LINK_DAYS` and every new link gets `expires_at` (backend/app/utils/portal_links.py:15); every public lookup refuses an expired link with 410 (:31). Reused work-order links get a fresh expiry when they lapse (backend/app/routers/work_orders.py:60).

## Connected to
- points at: estimate, change order, estimate (work order)
- triggers: status writes on the estimate or CO, approval (process), owner notification email, AI event dispatch (estimate approve only)

## If you change this
- **Hits:** both portal routers, the work-order public route (backend/app/routers/work_orders.py:179), the two portal pages (frontend/src/pages/CustomerPortalPage.jsx, ChangeOrderPortalPage.jsx), which hide the buttons using the same open set.
- **Does not hit:** authenticated API auth. Portal routes never see a JWT.

## Surfaces
Homeowners (public), crews (work orders), owner notification emails, signed PDFs.

## See
backend/app/routers/customer_portal.py
