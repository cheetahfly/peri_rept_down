# -*- coding: utf-8 -*-
"""Tests for enhanced Comparator with item_code tracking and detailed reports."""

from extraction.ground_truth.comparator import (
    compare_stock,
    ItemComparison,
    ComparisonResult,
)


def test_item_comparison_has_code_fields():
    """ItemComparison dataclass has ground_truth_code and extracted_item_code fields."""
    item = ItemComparison(
        ground_truth_name="货币资金",
        ground_truth_value=1000.0,
        extracted_name="货币资金",
        extracted_value=1000.0,
        match_type="exact",
        value_error_pct=0.0,
        ground_truth_code="F033N",
        extracted_item_code="F033N",
    )
    assert item.ground_truth_code == "F033N"
    assert item.extracted_item_code == "F033N"


def test_item_comparison_code_fields_default_none():
    """ground_truth_code and extracted_item_code default to None."""
    item = ItemComparison(
        ground_truth_name="存货",
        ground_truth_value=500.0,
        extracted_name=None,
        extracted_value=None,
        match_type="missing",
    )
    assert item.ground_truth_code is None
    assert item.extracted_item_code is None


def test_detailed_report_structure():
    """detailed_report() returns the expected keys and structure."""
    result = ComparisonResult("600519", 2020, "balance_sheet")
    result.items.append(ItemComparison(
        ground_truth_name="货币资金",
        ground_truth_value=1000.0,
        extracted_name="货币资金",
        extracted_value=1000.0,
        match_type="exact",
        value_error_pct=0.0,
        ground_truth_code="F033N",
    ))
    result.items.append(ItemComparison(
        ground_truth_name="应收账款",
        ground_truth_value=500.0,
        extracted_name=None,
        extracted_value=None,
        match_type="missing",
        ground_truth_code="F034N",
    ))
    result.items.append(ItemComparison(
        ground_truth_name="",
        ground_truth_value=None,
        extracted_name="其他流动资产",
        extracted_value=200.0,
        match_type="unmatched",
        extracted_item_code="F099N",
    ))

    report = result.detailed_report()
    assert report["stock_code"] == "600519"
    assert report["year"] == 2020
    assert report["statement_type"] == "balance_sheet"
    assert "coverage" in report
    assert "value_accuracy" in report
    assert "missing_items" in report
    assert "unmatched_items" in report
    assert "value_diffs" in report


def test_detailed_report_missing_items():
    """detailed_report() lists missing items with codes."""
    result = ComparisonResult("600519", 2020, "balance_sheet")
    result.items.append(ItemComparison(
        ground_truth_name="应收账款",
        ground_truth_value=500.0,
        extracted_name=None,
        extracted_value=None,
        match_type="missing",
        ground_truth_code="F034N",
    ))

    report = result.detailed_report()
    assert len(report["missing_items"]) == 1
    mi = report["missing_items"][0]
    assert mi["name"] == "应收账款"
    assert mi["code"] == "F034N"
    assert mi["expected_value"] == 500.0


def test_detailed_report_unmatched_items():
    """detailed_report() lists unmatched extracted items with codes."""
    result = ComparisonResult("600519", 2020, "balance_sheet")
    result.items.append(ItemComparison(
        ground_truth_name="",
        ground_truth_value=None,
        extracted_name="其他流动资产",
        extracted_value=200.0,
        match_type="unmatched",
        extracted_item_code="F099N",
    ))

    report = result.detailed_report()
    assert len(report["unmatched_items"]) == 1
    ui = report["unmatched_items"][0]
    assert ui["name"] == "其他流动资产"
    assert ui["code"] == "F099N"
    assert ui["value"] == 200.0


def test_detailed_report_value_diffs():
    """detailed_report() captures value diffs for matched items with error > 1%."""
    result = ComparisonResult("600519", 2020, "balance_sheet")
    # Exact match with 0% error -- should NOT appear in value_diffs
    result.items.append(ItemComparison(
        ground_truth_name="货币资金",
        ground_truth_value=1000.0,
        extracted_name="货币资金",
        extracted_value=1000.0,
        match_type="exact",
        value_error_pct=0.0,
        ground_truth_code="F033N",
    ))
    # Fuzzy match with 5% error -- should appear in value_diffs
    result.items.append(ItemComparison(
        ground_truth_name="存货",
        ground_truth_value=500.0,
        extracted_name="存货",
        extracted_value=525.0,
        match_type="fuzzy",
        value_error_pct=5.0,
        ground_truth_code="F035N",
    ))

    report = result.detailed_report()
    assert len(report["value_diffs"]) == 1
    vd = report["value_diffs"][0]
    assert vd["name"] == "存货"
    assert vd["code"] == "F035N"
    assert vd["ground_truth_value"] == 500.0
    assert vd["extracted_value"] == 525.0
    assert vd["error_pct"] == 5.0


def test_detailed_report_empty_result():
    """detailed_report() on empty result returns empty lists."""
    result = ComparisonResult("000001", 2021, "income_statement")
    report = result.detailed_report()
    assert report["missing_items"] == []
    assert report["unmatched_items"] == []
    assert report["value_diffs"] == []


def test_compare_stock_populates_ground_truth_code():
    """compare_stock() populates ground_truth_code when decode_map is provided."""
    gt_data = {
        "货币资金": 1000.0,
        "应收账款": 500.0,
        "存货": 300.0,
    }
    ext_data = {
        "货币资金": 1000.0,
        "应收账款": 500.0,
        "存货": 300.0,
    }
    decode_map = {
        "F033N": "货币资金",
        "F034N": "应收账款",
        "F035N": "存货",
    }

    result = compare_stock(
        gt_data, ext_data, {},
        stock_code="600519", year=2020, statement_type="balance_sheet",
        decode_map=decode_map,
    )

    # All three items should have ground_truth_code set
    by_name = {i.ground_truth_name: i for i in result.items}
    assert by_name["货币资金"].ground_truth_code == "F033N"
    assert by_name["应收账款"].ground_truth_code == "F034N"
    assert by_name["存货"].ground_truth_code == "F035N"


def test_compare_stock_code_none_without_decode_map():
    """compare_stock() leaves ground_truth_code as None when no decode_map."""
    gt_data = {"货币资金": 1000.0}
    ext_data = {"货币资金": 1000.0}

    result = compare_stock(gt_data, ext_data, {})

    assert result.items[0].ground_truth_code is None


def test_compare_stock_detailed_report_end_to_end():
    """End-to-end: compare_stock with decode_map -> detailed_report."""
    gt_data = {
        "货币资金": 1000.0,
        "应收账款": 500.0,
        "在建工程": 200.0,
    }
    ext_data = {
        "货币资金": 1000.0,
        "应收账款": 520.0,  # 4% error -- will be in value_diffs
        # 在建工程 missing from extracted
    }
    decode_map = {
        "F033N": "货币资金",
        "F034N": "应收账款",
        "F036N": "在建工程",
    }

    result = compare_stock(
        gt_data, ext_data, {},
        stock_code="600519", year=2020, statement_type="balance_sheet",
        decode_map=decode_map,
    )

    report = result.detailed_report()

    # Coverage: 2 matched / 3 total = 0.6667
    assert abs(report["coverage"] - 2.0 / 3.0) < 0.01

    # Missing items: 在建工程
    assert len(report["missing_items"]) == 1
    assert report["missing_items"][0]["code"] == "F036N"

    # Value diffs: 应收账款 with 4% error
    assert len(report["value_diffs"]) == 1
    assert report["value_diffs"][0]["code"] == "F034N"
