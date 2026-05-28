# -*- coding: utf-8 -*-
"""End-to-end integration tests for the Tidy Data pipeline."""

def test_rds_tidy_data_for_600519_2020():
    """Verify 600519 2020 annual report Tidy Data output"""
    from extraction.ground_truth.rds_loader import RdsLoader

    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    loader = RdsLoader(RDS_DIR)

    # Test all three statement types return Tidy Data
    for st_type in ["income_statement", "balance_sheet", "cash_flow"]:
        result = loader.load_stock_data_tidy("600519", 2020, st_type)
        assert len(result) > 0, f"{st_type} returned empty"

        # Verify required fields
        for item in result:
            assert "item_code" in item
            assert "item_name" in item
            assert "display_order" in item
            assert item["stock_code"] == "600519"
            assert item["report_year"] == 2020
            assert item["statement_type"] == st_type

    # Verify income_statement has two "利息收入" with different item_codes
    is_result = loader.load_stock_data_tidy("600519", 2020, "income_statement")
    interest_items = [r for r in is_result if "利息收入" in r["item_name"]]
    assert len(interest_items) == 2

    codes = {r["item_code"] for r in interest_items}
    assert len(codes) == 2, f"Should have 2 different item_codes for '利息收入', got {codes}"

    # Verify values are different
    values = {r["item_code"]: r["value"] for r in interest_items}
    assert values["F033N"] != values["F063N"], "F033N and F063N should have different values"


def test_display_order_sequential():
    """Verify display_order is sequential (0, 1, 2, ...)"""
    from extraction.ground_truth.rds_loader import RdsLoader

    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    loader = RdsLoader(RDS_DIR)

    result = loader.load_stock_data_tidy("600519", 2020, "income_statement")

    # Extract display_order values and verify they are sequential starting from 0
    orders = [r["display_order"] for r in result]
    assert orders == list(range(len(orders))), f"display_order should be sequential, got {orders}"


def test_aliases_hierarchical_integration():
    """Verify aliases work with statement_type x report_type"""
    from extraction.config import get_aliases

    # Test various combinations
    assert get_aliases("income_statement", "annual")
    assert get_aliases("balance_sheet", "annual")
    assert get_aliases("cash_flow", "annual")
    assert get_aliases("income_statement", "half_year")