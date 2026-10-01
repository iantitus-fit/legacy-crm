from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.estimate import Estimate
from app.models.estimate_line_item import EstimateLineItem

TWO_PLACES = Decimal("0.01")


def calculate_line_total(qty: Decimal, unit_price: Decimal) -> Decimal:
    """Calculate a single line item total: qty * unit_price, rounded to 2 places."""
    return (Decimal(str(qty)) * Decimal(str(unit_price))).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )


def recalculate_estimate(db: Session, estimate_id: int) -> Estimate:
    """Recompute all totals for an estimate from its line items.

    Updates each line_total, then subtotal, tax, and total on the estimate.
    """
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if estimate is None:
        raise ValueError(f"Estimate {estimate_id} not found")

    line_items = (
        db.query(EstimateLineItem)
        .filter(EstimateLineItem.estimate_id == estimate_id)
        .all()
    )

    for item in line_items:
        qty = Decimal(str(item.qty or 0))
        unit_price = Decimal(str(item.unit_price or 0))
        item.line_total = calculate_line_total(qty, unit_price)

    subtotal = sum(
        (Decimal(str(item.line_total)) for item in line_items),
        Decimal("0"),
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    if estimate.tax_included:
        tax = Decimal("0")
        total = subtotal
    else:
        tax_rate = Decimal(str(estimate.tax_rate or 0))
        tax = (subtotal * tax_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        total = (subtotal + tax).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    estimate.subtotal = subtotal
    estimate.tax = tax
    estimate.total = total

    db.commit()
    db.refresh(estimate)
    return estimate
