from decimal import Decimal

from app.services.estimate_calculator import calculate_line_total


def test_line_total_basic():
    assert calculate_line_total(Decimal("2"), Decimal("50.00")) == Decimal("100.00")


def test_line_total_decimal_qty():
    assert calculate_line_total(Decimal("3.5"), Decimal("12.75")) == Decimal("44.63")


def test_line_total_zero_qty():
    assert calculate_line_total(Decimal("0"), Decimal("100.00")) == Decimal("0.00")


def test_line_total_zero_price():
    assert calculate_line_total(Decimal("5"), Decimal("0")) == Decimal("0.00")


def test_line_total_rounding_half_up():
    # 3 * 10.005 = 30.015 -> should round to 30.02 (ROUND_HALF_UP)
    assert calculate_line_total(Decimal("3"), Decimal("10.005")) == Decimal("30.02")


def test_line_total_large_values():
    result = calculate_line_total(Decimal("100"), Decimal("9999.99"))
    assert result == Decimal("999999.00")


def test_line_total_small_values():
    result = calculate_line_total(Decimal("0.5"), Decimal("0.01"))
    assert result == Decimal("0.01")
