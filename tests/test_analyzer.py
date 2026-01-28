"""
Test script for analyzer module.

Run basic tests without database to verify function signatures.
"""

from decimal import Decimal

from scraper.utils.analyzer import (
    _get_action_suggestion,
    _get_stock_change_message,
    PriceChangeResult,
    StockChangeResult,
    SitePrice,
)


def test_action_suggestions():
    """Test action suggestion logic."""
    # Critical decrease
    msg, level = _get_action_suggestion(Decimal("-15"))
    assert "ACIL" in msg or "dust" in msg.lower()
    assert level == "critical"
    print("Critical decrease: OK")

    # Warning decrease
    msg, level = _get_action_suggestion(Decimal("-7"))
    assert "UYARI" in msg or "hafif" in msg.lower()
    assert level == "warning"
    print("Warning decrease: OK")

    # Info increase
    msg, level = _get_action_suggestion(Decimal("15"))
    assert "arttird" in msg.lower() or "BILGI" in msg
    assert level == "info"
    print("Info increase: OK")

    # Minor increase
    msg, level = _get_action_suggestion(Decimal("7"))
    assert level == "info"
    print("Minor increase: OK")

    # Below threshold
    msg, level = _get_action_suggestion(Decimal("2"))
    assert msg is None
    assert level == "none"
    print("Below threshold: OK")


def test_stock_change_messages():
    """Test stock change message logic."""
    # Stock out
    change_type, msg = _get_stock_change_message("stokta", "tukendi")
    assert change_type == "stock_out"
    assert "FIRSAT" in msg or "tukendi" in msg.lower()
    print("Stock out: OK")

    # Stock in
    change_type, msg = _get_stock_change_message("tukendi", "stokta")
    assert change_type == "stock_in"
    assert "DIKKAT" in msg or "geld" in msg.lower()
    print("Stock in: OK")

    # Limited stock
    change_type, msg = _get_stock_change_message("stokta", "son birkaclar")
    assert change_type == "stock_low"
    print("Stock low: OK")


def test_named_tuples():
    """Test NamedTuple structures."""
    # PriceChangeResult
    result = PriceChangeResult(
        change_percent=Decimal("-10.5"),
        old_price=Decimal("100"),
        action_suggestion="Test action",
        alert_level="warning"
    )
    assert result.change_percent == Decimal("-10.5")
    assert result.old_price == Decimal("100")
    print("PriceChangeResult: OK")

    # StockChangeResult
    result = StockChangeResult(
        previous_status="stokta",
        change_type="stock_out",
        message="Rakip stoku tukendi!"
    )
    assert result.previous_status == "stokta"
    assert result.change_type == "stock_out"
    print("StockChangeResult: OK")

    # SitePrice
    price = SitePrice(
        site_name="cafemarkt",
        price=Decimal("15000"),
        currency="TRY",
        stock_status="stokta",
        url="https://example.com/product"
    )
    assert price.site_name == "cafemarkt"
    assert price.price == Decimal("15000")
    print("SitePrice: OK")


if __name__ == "__main__":
    print("Testing analyzer module...")
    print()
    test_action_suggestions()
    print()
    test_stock_change_messages()
    print()
    test_named_tuples()
    print()
    print("All tests passed!")
