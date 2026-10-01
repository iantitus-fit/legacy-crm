# Data in this repo

Everything here is safe to publish. Nothing in this folder came from a real customer record.

| File | What it is | Real or synthetic |
|---|---|---|
| `sample/contacts_report.csv` | AccuLynx-style contacts export, 220 rows | Synthetic |
| `sample/jobs_report.csv` | AccuLynx-style jobs export, 72 rows | Synthetic |
| `sample/invoice_report.csv` | AccuLynx-style invoice export | Synthetic |
| `sample/ar_age_report.csv` | AccuLynx-style A/R aging export | Synthetic |
| `materials_*.csv` | Supplier price lists after OCR | Product descriptions are real catalog names. Item numbers and prices are synthetic. |

## How the sample data was made

`scripts/generate_sample_data.py` writes the four `sample/` files. It keeps the column layout of the
real AccuLynx exports and the quirks the importer had to handle: phone numbers with and without
formatting, placeholder emails, ZIP+4 codes, double spaces inside job names. The shape of the pipeline
(most contacts early stage, one paid lead source dominating, a small tail of approved and invoiced
work) is modeled on the real business. The values are not.

- Names are random pairings from lists of common first and last names.
- Phone numbers come from the 555-0100 to 555-0199 block, which is reserved for fiction.
- Street names are invented. Town names are real places near the business.
- Emails use example.com, example.net and example.org, which are reserved for documentation.
- Dollar amounts are generated in ranges, not copied.

The script is deterministic. Run it again with the same seed and you get the same files.

## Supplier prices

The materials files began as scanned supplier price lists that were OCR'd into CSV. Rows the OCR could
not trust carry a note in `ocr_flag`. For this public copy each item number was replaced and each price
was moved up or down by a random amount between roughly 20 percent below and 20 percent above, so the
library behaves like the real one without exposing an account's negotiated pricing.
