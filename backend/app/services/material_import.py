import csv
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.price_list import PriceList

# Leading OCR artifact characters to strip
_OCR_JUNK_RE = re.compile(r"^[\u2018\u2019({]+")


def clean_item_number(raw: str) -> str:
    """Strip leading OCR artifact characters and whitespace from item numbers."""
    return _OCR_JUNK_RE.sub("", raw).strip()


def import_materials_csv(
    db: Session,
    file_path: str,
    source_file: Optional[str] = None,
    effective_date: Optional[date] = None,
    expiration_date: Optional[date] = None,
    user_id: Optional[int] = None,
) -> Dict:
    """Import materials from a CSV file.

    CSV must have columns: item_number, description, unit_price, uom, category, source, ocr_flag

    Returns dict with keys: price_lists_created, materials_imported, errors
    """
    errors: List[str] = []
    price_list_cache: Dict[str, PriceList] = {}
    imported_count = 0

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=2):
            source_name = (row.get("source") or "").strip()
            if not source_name:
                errors.append(f"Row {row_num}: missing source")
                continue

            # Get or create price list for this source
            if source_name not in price_list_cache:
                existing = (
                    db.query(PriceList)
                    .filter(PriceList.name == source_name)
                    .first()
                )
                if existing:
                    price_list_cache[source_name] = existing
                else:
                    pl = PriceList(
                        name=source_name,
                        source_file=source_file,
                        effective_date=effective_date,
                        expiration_date=expiration_date,
                        imported_by_user_id=user_id,
                    )
                    db.add(pl)
                    db.flush()
                    price_list_cache[source_name] = pl

            # Parse fields
            raw_item = (row.get("item_number") or "").strip()
            description = (row.get("description") or "").strip()
            raw_price = (row.get("unit_price") or "").strip()
            uom = (row.get("uom") or "").strip() or None
            category = (row.get("category") or "").strip()
            ocr_flag = (row.get("ocr_flag") or "").strip() or None

            if not raw_item or not description or not raw_price or not category:
                errors.append(
                    f"Row {row_num}: missing required field "
                    f"(item_number={raw_item!r}, description={description!r}, "
                    f"unit_price={raw_price!r}, category={category!r})"
                )
                continue

            item_number = clean_item_number(raw_item)

            try:
                unit_price = Decimal(raw_price)
            except InvalidOperation:
                errors.append(f"Row {row_num}: invalid price {raw_price!r}")
                continue

            material = Material(
                price_list_id=price_list_cache[source_name].id,
                item_number=item_number,
                description=description,
                unit_price=unit_price,
                uom=uom,
                category=category,
                ocr_flag=ocr_flag,
            )
            db.add(material)
            imported_count += 1

    db.commit()

    return {
        "price_lists_created": len(price_list_cache),
        "materials_imported": imported_count,
        "errors": errors,
    }
