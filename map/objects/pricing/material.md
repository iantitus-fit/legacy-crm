---
type: object
cluster: pricing
status: live
verified: 2026-10-01 · public copy of 7fbda4a + money-path fixes
entity: backend/app/models/material.py
---
# material

**Type:** object · **Mark:** live · **Checked:** 2026-10-01 · **Where:** backend/app/models/material.py

## One sentence
One row of a supplier price list (`materials`), grouped under a `price_lists` row per supplier.

## Why this shape
The supplier lists arrived as scanned PDFs. They were OCR'd into CSV, and rows the OCR could not
trust carry an `ocr_flag` for human review instead of being silently dropped.

## Shape
- `materials`: `item_number`, `description`, `unit_price` (supplier cost), `uom`, `category`, `ocr_flag`, `is_active` (backend/app/models/material.py:18-34).
- `price_lists`: `name`, `source_file`, effective/expiration dates (backend/app/models/price_list.py).
- Import: `import_materials_csv` (backend/app/services/material_import.py:21) via `POST /api/materials/import` (backend/app/routers/materials.py:59) or `backend/scripts/import_materials.py`.
- Public copy: `data/materials_*.csv` keep real product descriptions but carry synthetic item numbers and prices.

## Connected to
- owned-by: price list
- read-by: the template item picker, which copies `unit_price` into the template item's `unit_cost` (frontend/src/pages/TemplateBuilderPage.jsx:539)
- looks-like-but-is-not: a line item price. Margin is applied later, in the template.

## If you change this
- **Hits:** materials library pages, the template picker, the import endpoint and script.
- **Does not hit:** saved templates or any estimate. Prices flow forward only when a person re-adds the item.

## Surfaces
Materials library UI, materials API, import script, tests in backend/tests/test_material_import*.py.

## See
backend/app/services/material_import.py
