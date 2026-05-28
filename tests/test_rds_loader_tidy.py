# -*- coding: utf-8 -*-
"""Tests for RdsLoader.load_stock_data_tidy() method."""

def test_load_stock_data_tidy_returns_correct_fields():
    """Verify Tidy Data returns all required fields"""
    from extraction.ground_truth.rds_loader import RdsLoader

    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    loader = RdsLoader(RDS_DIR)

    result = loader.load_stock_data_tidy("600519", 2020, "income_statement")

    assert len(result) > 0
    item = result[0]
    required_fields = ["stock_code", "report_year", "report_type", "statement_type",
                       "item_code", "item_name", "value", "display_order"]
    for field in required_fields:
        assert field in item, f"Missing field: {field}"


def test_load_stock_data_tidy_f033n_and_f063n_different():
    """Verify F033N and F063N (two '利息收入') are correctly distinguished"""
    from extraction.ground_truth.rds_loader import RdsLoader

    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    loader = RdsLoader(RDS_DIR)

    result = loader.load_stock_data_tidy("600519", 2020, "income_statement")

    # Find two "利息收入"
    interest_income_items = [r for r in result if "利息收入" in r["item_name"]]
    assert len(interest_income_items) == 2

    # Verify item_code is different
    item_codes = {r["item_code"] for r in interest_income_items}
    assert "F033N" in item_codes
    assert "F063N" in item_codes

    # Verify values are different
    values = {r["item_code"]: r["value"] for r in interest_income_items}
    assert values["F033N"] != values["F063N"]


def test_load_stock_data_tidy_sorted_by_display_order():
    """Verify results are sorted by display_order"""
    from extraction.ground_truth.rds_loader import RdsLoader

    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    loader = RdsLoader(RDS_DIR)

    result = loader.load_stock_data_tidy("600519", 2020, "income_statement")

    orders = [r["display_order"] for r in result]
    assert orders == sorted(orders), "Results should be sorted by display_order"