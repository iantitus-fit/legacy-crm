import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def calculate_item(
    unit_cost: Decimal,
    margin_pct: Decimal,
    waste_pct: Decimal,
    measurement_type: Optional[str],
    conversion_factor: Decimal,
    default_qty: Optional[Decimal],
    measurements: Dict[str, Decimal],
) -> Dict:
    """Calculate a single template item's quantity, sell price, and line total.

    Returns dict with: qty, unit_price, line_total, raw_qty, waste_applied,
    measurement_value.
    """
    unit_cost = Decimal(str(unit_cost))
    margin_pct = Decimal(str(margin_pct))
    waste_pct = Decimal(str(waste_pct))
    conversion_factor = Decimal(str(conversion_factor))

    # Step 1: Determine raw quantity
    measurement_value = None
    if measurement_type and measurement_type in measurements:
        measurement_value = Decimal(str(measurements[measurement_type]))
        raw_qty = (measurement_value * conversion_factor).quantize(
            FOUR_PLACES, rounding=ROUND_HALF_UP
        )
    elif measurement_type is None and default_qty is not None:
        raw_qty = Decimal(str(default_qty))
    else:
        # Missing measurement or no default — zero qty
        return {
            "qty": 0,
            "unit_price": (
                unit_cost * (Decimal("1") + margin_pct / Decimal("100"))
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            "line_total": Decimal("0.00"),
            "raw_qty": Decimal("0.0000"),
            "waste_applied": Decimal("0.0000"),
            "measurement_value": measurement_value,
        }

    # Step 2: Apply waste factor
    waste_applied = (
        raw_qty * (Decimal("1") + waste_pct / Decimal("100"))
    ).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)

    # Step 3: Round up to whole units
    qty = math.ceil(float(waste_applied))

    # Step 4: Calculate sell price (unit_cost + margin)
    sell_price = (
        unit_cost * (Decimal("1") + margin_pct / Decimal("100"))
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Step 5: Line total
    line_total = (Decimal(str(qty)) * sell_price).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    return {
        "qty": qty,
        "unit_price": sell_price,
        "line_total": line_total,
        "raw_qty": raw_qty,
        "waste_applied": waste_applied,
        "measurement_value": measurement_value,
    }


def calculate_template_preview(
    items: List[Dict],
    measurements: Dict[str, Decimal],
) -> Dict:
    """Calculate a full template preview from items and measurements.

    Each item dict should have: description, category, unit_cost, uom,
    margin_pct, waste_pct, measurement_type, conversion_factor, default_qty.

    Returns dict with: items (list of calculated line items), subtotal, item_count.
    """
    result_items = []
    subtotal = Decimal("0.00")

    for item in items:
        calc = calculate_item(
            unit_cost=item["unit_cost"],
            margin_pct=item["margin_pct"],
            waste_pct=item["waste_pct"],
            measurement_type=item.get("measurement_type"),
            conversion_factor=item["conversion_factor"],
            default_qty=item.get("default_qty"),
            measurements=measurements,
        )
        result_items.append(
            {
                "description": item["description"],
                "category": item["category"],
                "qty": calc["qty"],
                "unit_price": calc["unit_price"],
                "line_total": calc["line_total"],
                "measurement_type": item.get("measurement_type"),
                "measurement_value": calc["measurement_value"],
                "raw_qty": calc["raw_qty"],
                "waste_applied": calc["waste_applied"],
                "uom": item.get("uom"),
            }
        )
        subtotal += calc["line_total"]

    return {
        "items": result_items,
        "subtotal": subtotal.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "item_count": len(result_items),
    }
