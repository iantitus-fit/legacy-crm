import math
from decimal import Decimal

import pytest

from app.services.template_calculator import (
    calculate_item,
    calculate_template_preview,
)


class TestCalculateItem:
    """Test the single-item calculation function."""

    def test_measurement_based_shingles(self):
        """32.5 sq area * 3 bundles/sq = 97.5, +10% waste = 107.25, ceil = 108.
        Sell price: 117.96 * 1.46 = 172.2216 -> 172.22.
        Line total: 108 * 172.22 = 18599.76."""
        result = calculate_item(
            unit_cost=Decimal("117.96"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("10.00"),
            measurement_type="total_area",
            conversion_factor=Decimal("3.0000"),
            default_qty=None,
            measurements={"total_area": Decimal("32.5")},
        )
        assert result["qty"] == 108
        assert result["unit_price"] == Decimal("172.22")
        assert result["line_total"] == Decimal("18599.76")
        assert result["raw_qty"] == Decimal("97.5000")
        assert result["waste_applied"] == Decimal("107.2500")
        assert result["measurement_value"] == Decimal("32.5")

    def test_fixed_qty_labor(self):
        """No measurement_type, default_qty=1. Waste 0%. Margin 46%.
        Qty: ceil(1 * 1.0) = 1. Sell price: 500 * 1.46 = 730.00.
        Line total: 730.00."""
        result = calculate_item(
            unit_cost=Decimal("500.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("0.00"),
            measurement_type=None,
            conversion_factor=Decimal("1.0000"),
            default_qty=Decimal("1.00"),
            measurements={},
        )
        assert result["qty"] == 1
        assert result["unit_price"] == Decimal("730.00")
        assert result["line_total"] == Decimal("730.00")

    def test_ridge_cap_conversion(self):
        """45 LF ridge / 33 LF per bundle = 1.3636..., +10% = 1.5, ceil = 2.
        Sell price: 68.50 * 1.46 = 100.01.
        Line total: 2 * 100.01 = 200.02."""
        result = calculate_item(
            unit_cost=Decimal("68.50"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("10.00"),
            measurement_type="ridge",
            conversion_factor=Decimal("0.0303"),  # 1/33
            default_qty=None,
            measurements={"ridge": Decimal("45.0")},
        )
        # 45 * 0.0303 = 1.3635, * 1.10 = 1.49985, ceil = 2
        assert result["qty"] == 2
        assert result["unit_price"] == Decimal("100.01")
        assert result["line_total"] == Decimal("200.02")

    def test_zero_waste(self):
        """Items with 0% waste: qty = ceil(raw_qty)."""
        result = calculate_item(
            unit_cost=Decimal("45.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("0.00"),
            measurement_type="total_area",
            conversion_factor=Decimal("1.0000"),
            default_qty=None,
            measurements={"total_area": Decimal("32.5")},
        )
        # 32.5 * 1.0 = 32.5, * 1.0 = 32.5, ceil = 33
        assert result["qty"] == 33

    def test_missing_measurement_returns_zero_qty(self):
        """If measurement_type is set but that measurement is missing, qty = 0."""
        result = calculate_item(
            unit_cost=Decimal("50.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("10.00"),
            measurement_type="valley",
            conversion_factor=Decimal("1.0000"),
            default_qty=None,
            measurements={"total_area": Decimal("32.5")},
        )
        assert result["qty"] == 0
        assert result["line_total"] == Decimal("0.00")

    def test_no_measurement_type_no_default_qty(self):
        """No measurement_type and no default_qty: qty = 0."""
        result = calculate_item(
            unit_cost=Decimal("50.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("0.00"),
            measurement_type=None,
            conversion_factor=Decimal("1.0000"),
            default_qty=None,
            measurements={},
        )
        assert result["qty"] == 0
        assert result["line_total"] == Decimal("0.00")

    def test_zero_margin(self):
        """0% margin: sell price = cost price."""
        result = calculate_item(
            unit_cost=Decimal("100.00"),
            margin_pct=Decimal("0.00"),
            waste_pct=Decimal("0.00"),
            measurement_type=None,
            conversion_factor=Decimal("1.0000"),
            default_qty=Decimal("5.00"),
            measurements={},
        )
        assert result["unit_price"] == Decimal("100.00")
        assert result["qty"] == 5
        assert result["line_total"] == Decimal("500.00")

    def test_high_conversion_factor(self):
        """Nails: 180 LF eave * 0.5 box/LF = 90, +5% waste = 94.5, ceil = 95."""
        result = calculate_item(
            unit_cost=Decimal("9.50"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("5.00"),
            measurement_type="eave",
            conversion_factor=Decimal("0.5000"),
            default_qty=None,
            measurements={"eave": Decimal("180.0")},
        )
        assert result["qty"] == 95
        assert result["unit_price"] == Decimal("13.87")


class TestCalculateTemplatePreview:
    """Test the full template preview calculation."""

    def test_basic_preview(self):
        """Two items: one measurement-based, one fixed-qty."""
        items = [
            {
                "description": "Shingles",
                "category": "Roofing",
                "unit_cost": Decimal("100.00"),
                "uom": "BD",
                "margin_pct": Decimal("46.00"),
                "waste_pct": Decimal("10.00"),
                "measurement_type": "total_area",
                "conversion_factor": Decimal("3.0000"),
                "default_qty": None,
            },
            {
                "description": "Labor",
                "category": "Labor",
                "unit_cost": Decimal("500.00"),
                "uom": None,
                "margin_pct": Decimal("46.00"),
                "waste_pct": Decimal("0.00"),
                "measurement_type": None,
                "conversion_factor": Decimal("1.0000"),
                "default_qty": Decimal("1.00"),
            },
        ]
        measurements = {"total_area": Decimal("10.0")}
        result = calculate_template_preview(items, measurements)

        assert result["item_count"] == 2
        assert len(result["items"]) == 2

        # Shingles: 10 * 3 = 30, +10% = 33, ceil = 33
        # Price: 100 * 1.46 = 146.00
        # Total: 33 * 146.00 = 4818.00
        shingles = result["items"][0]
        assert shingles["qty"] == 33
        assert shingles["unit_price"] == Decimal("146.00")
        assert shingles["line_total"] == Decimal("4818.00")

        # Labor: default_qty 1, no waste = 1
        # Price: 500 * 1.46 = 730.00
        labor = result["items"][1]
        assert labor["qty"] == 1
        assert labor["line_total"] == Decimal("730.00")

        assert result["subtotal"] == Decimal("5548.00")

    def test_empty_items(self):
        result = calculate_template_preview([], {"total_area": Decimal("10.0")})
        assert result["item_count"] == 0
        assert result["subtotal"] == Decimal("0.00")
