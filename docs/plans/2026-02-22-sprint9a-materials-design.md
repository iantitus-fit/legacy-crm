# Sprint 9a: Materials Database & Import — Design Document

**Date:** 2026-02-22
**Sprint:** 9a
**Status:** Approved

## Overview

Add a master materials library to the CRM. Dale needs to browse, search, and edit ~1,550 material items imported from three ABC Supply price lists (roofing, siding, accessories). Materials are organized by price list with expiration tracking. OCR-scanned items are flagged for review.

## Data Model

### `price_lists` table

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String(100), unique | e.g. "ABC Roofing" |
| source_file | String(255), nullable | Original CSV filename |
| effective_date | Date, nullable | When prices took effect |
| expiration_date | Date, nullable | When prices expire |
| imported_at | DateTime(tz) | server_default=now() |
| imported_by_user_id | Integer FK → users, nullable | Who uploaded |

### `materials` table

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| price_list_id | Integer FK → price_lists | CASCADE delete |
| item_number | String(50) | Cleaned of OCR artifacts on import |
| description | String(500) | |
| unit_price | Numeric(12,2) | |
| uom | String(10), nullable | PC/SQ/BX/RL/BD or blank |
| category | String(100) | 20 categories from CSV |
| ocr_flag | String(200), nullable | Review notes from OCR scan |
| is_active | Boolean, default true | Soft delete |
| created_at | DateTime(tz) | server_default=now() |
| updated_at | DateTime(tz) | server_default=now() |

**Indexes:**
- `ix_materials_price_list_item` on (price_list_id, item_number)
- `ix_materials_category` on (category)

## CSV Import

- Auto-strip leading OCR artifact characters (`'` U+2018, `(`, `{`) from item_numbers
- Import all rows including those with missing UOM (editable in admin UI)
- Create one price_list record per unique `source` value
- Preserve ocr_flag values from CSV
- Available as both CLI script and API endpoint

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/materials | Paginated list with search, category/price_list/ocr filters |
| GET | /api/materials/{id} | Single material |
| POST | /api/materials | Create single material |
| PUT | /api/materials/{id} | Update material |
| DELETE | /api/materials/{id} | Soft delete (is_active=false) |
| POST | /api/materials/import | CSV upload → creates price_list + materials |
| GET | /api/materials/categories | List distinct categories with counts |
| GET | /api/price-lists | List all price lists with item counts |
| PUT | /api/price-lists/{id} | Update price list (name, dates) |

## Admin UI

**Route:** `/materials` in JOBS sidebar section (after Estimates)

**Layout:**
1. Price list summary cards at top (name, count, expiration status with color coding)
2. Filter bar: category dropdown, source dropdown, "Needs Review" toggle, search
3. Table: Item #, Description, Unit Price, UOM, Category, Source, Status, Actions
4. Inline edit via row expansion or modal
5. Import button opens modal: CSV upload, price list name, effective/expiration dates

## Data Quality (from CSV analysis)

- 1,550 total rows across 3 sources
- 20 distinct categories
- 271 rows missing UOM (17.5%, mostly accessories)
- 138 rows with ocr_flag (needs review)
- 128 item_numbers with leading smart-quote artifacts (auto-cleaned)
- 2 duplicate item_numbers (imported as-is, flagged)
