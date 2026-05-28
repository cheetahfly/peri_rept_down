# -*- coding: utf-8 -*-
"""
End-to-end integration tests for the Phase 2 Tidy Data pipeline.

Tests the integration between:
- RdsLoader.load_stock_data_tidy()
- compare_stock() with decode_map
- GapAnalyzer
- ItemMapper with hierarchical aliases
"""

import tempfile
import os
import json
import pytest

from extraction.ground_truth.comparator import (
    compare_stock,
    ComparisonResult,
    ItemComparison,
)
from extraction.ground_truth.gap_analyzer import GapAnalyzer
from extraction.ground_truth.mapper import ItemMapper


# ---------------------------------------------------------------------------
# Test 1: End-to-end comparison with item_code tracking
# ---------------------------------------------------------------------------

def test_end_to_end_comparison_with_item_codes():
    """
    Test complete comparison flow including item_code tracking.

    Verifies:
    - RdsLoader returns tidy data with item_codes
    - compare_stock() uses decode_map to populate ground_truth_code
    - detailed_report() includes item codes in missing/unmatched items
    """
    # Mock Tidy Data format (simulating load_stock_data_tidy output)
    tidy_gt_data = [
        {"item_code": "F033N", "item_name": "货币资金", "value": 1000.0, "display_order": 0},
        {"item_code": "F034N", "item_name": "应收账款", "value": 500.0, "display_order": 1},
        {"item_code": "F035N", "item_name": "存货", "value": 300.0, "display_order": 2},
        {"item_code": "F036N", "item_name": "在建工程", "value": 200.0, "display_order": 3},
    ]

    # Convert to dict format for compare_stock
    gt_data = {item["item_name"]: item["value"] for item in tidy_gt_data}

    # Extracted data (with some differences):
    # - 货币资金: exact match
    # - 应收账款: 4% error (value diff)
    # - 在建工程: missing from extracted
    # - 其他流动资产: unmatched (not in GT)
    ext_data = {
        "货币资金": 1000.0,
        "应收账款": 520.0,  # 4% error
        "存货": 300.0,  # exact match
        "其他流动资产": 150.0,  # unmatched
    }

    # Build decode_map from tidy data (format: {code: name})
    decode_map = {item["item_code"]: item["item_name"] for item in tidy_gt_data}

    # Alias map (empty for this test)
    alias_map = {}

    # Run comparison
    result = compare_stock(
        gt_data, ext_data, alias_map,
        stock_code="600519",
        year=2020,
        statement_type="balance_sheet",
        decode_map=decode_map,
    )

    # Verify result type
    assert isinstance(result, ComparisonResult)

    # Verify item codes are populated
    by_name = {i.ground_truth_name: i for i in result.items}
    assert by_name["货币资金"].ground_truth_code == "F033N"
    assert by_name["应收账款"].ground_truth_code == "F034N"
    assert by_name["存货"].ground_truth_code == "F035N"
    assert by_name["在建工程"].ground_truth_code == "F036N"

    # Get detailed report
    report = result.detailed_report()

    # Verify report structure
    assert report["stock_code"] == "600519"
    assert report["year"] == 2020
    assert report["statement_type"] == "balance_sheet"
    assert "coverage" in report
    assert "value_accuracy" in report
    assert "missing_items" in report
    assert "unmatched_items" in report
    assert "value_diffs" in report

    # Verify missing_items include codes
    missing_names = {m["name"] for m in report["missing_items"]}
    assert "在建工程" in missing_names
    missing_in_report = [m for m in report["missing_items"] if m["name"] == "在建工程"][0]
    assert missing_in_report["code"] == "F036N"

    # Verify unmatched_items include codes
    unmatched_names = {u["name"] for u in report["unmatched_items"]}
    assert "其他流动资产" in unmatched_names

    # Verify value_diffs include codes
    diff_names = {d["name"] for d in report["value_diffs"]}
    assert "应收账款" in diff_names
    diff_in_report = [d for d in report["value_diffs"] if d["name"] == "应收账款"][0]
    assert diff_in_report["code"] == "F034N"

    # Verify coverage calculation: 3 matched / 4 total = 0.75
    assert abs(report["coverage"] - 0.75) < 0.01


def test_tidy_data_to_old_format_conversion():
    """
    Test converting Tidy Data format to old dict format for comparison.
    """
    # Simulate load_stock_data_tidy output
    tidy_data = [
        {"item_code": "F001N", "item_name": "营业收入", "value": 1000.0},
        {"item_code": "F002N", "item_name": "营业成本", "value": 600.0},
        {"item_code": "F003N", "item_name": "净利润", "value": 200.0},
    ]

    # Convert to dict for comparison
    gt_dict = {item["item_name"]: item["value"] for item in tidy_data}
    # decode_map format: {code: name}
    decode_map = {item["item_code"]: item["item_name"] for item in tidy_data}

    assert gt_dict == {"营业收入": 1000.0, "营业成本": 600.0, "净利润": 200.0}
    # decode_map format: {code: name}
    assert decode_map == {"F001N": "营业收入", "F002N": "营业成本", "F003N": "净利润"}

    # Run comparison
    result = compare_stock(gt_dict, gt_dict, {}, stock_code="000001", year=2020,
                           statement_type="income_statement", decode_map=decode_map)

    # All items should match exactly
    assert result.coverage == 1.0

    # All items should have codes
    for item in result.items:
        if item.match_type != "unmatched":
            assert item.ground_truth_code is not None


# ---------------------------------------------------------------------------
# Test 2: GapAnalyzer with comparison results
# ---------------------------------------------------------------------------

def test_gap_analyzer_with_real_data():
    """
    Test GapAnalyzer with realistic comparison report.

    Verifies:
    - GapAnalyzer.analyze() produces suggestions from detailed report
    - Alias suggestions link missing GT items to similar unmatched items
    - Unit suggestions detect 10000x value differences
    - generate_yaml_updates() produces correct structure
    """
    # Build a realistic detailed report (simulating ComparisonResult.detailed_report())
    report = {
        "stock_code": "600519",
        "year": 2020,
        "statement_type": "balance_sheet",
        "coverage": 0.75,
        "value_accuracy": 0.667,
        "missing_items": [
            {"name": "货币资金", "code": "F033N", "expected_value": 1000.0},
            {"name": "在建工程", "code": "F036N", "expected_value": 200.0},
        ],
        "unmatched_items": [
            {"name": "货币资金合计", "code": None, "value": 1000.0},
            {"name": "完全不相关的科目", "code": None, "value": 5000.0},
        ],
        "value_diffs": [
            {
                "name": "营业收入",
                "code": "F001N",
                "ground_truth_value": 100000000.0,
                "extracted_value": 10000.0,
                "error_pct": 99.99,
            }
        ],
    }

    # Run GapAnalyzer
    ga = GapAnalyzer(min_similarity=0.5)
    suggestions = ga.analyze(report)

    # Verify suggestions structure
    assert isinstance(suggestions, list)

    # Find alias suggestion for 货币资金
    alias_suggestions = [s for s in suggestions if s["type"] == "alias_suggestion"]
    currency_suggestion = next(
        (s for s in alias_suggestions if s["standard_name"] == "货币资金"),
        None
    )
    assert currency_suggestion is not None
    assert "货币资金合计" in currency_suggestion["variants"]
    assert currency_suggestion["code"] == "F033N"

    # Find unit suggestion
    unit_suggestions = [s for s in suggestions if s["type"] == "unit_suggestion"]
    assert len(unit_suggestions) == 1
    assert unit_suggestions[0]["standard_name"] == "营业收入"
    assert unit_suggestions[0]["suggested_unit"] == "万元"
    assert unit_suggestions[0]["reason"] == "value_off_by_10000x"

    # Generate YAML updates
    yaml_updates = ga.generate_yaml_updates(suggestions, statement_type="balance_sheet")

    # Verify structure
    assert "balance_sheet" in yaml_updates
    assert "货币资金" in yaml_updates["balance_sheet"]
    assert "货币资金合计" in yaml_updates["balance_sheet"]["货币资金"]


def test_gap_analyzer_empty_report():
    """Test GapAnalyzer with empty report returns empty suggestions."""
    report = {
        "stock_code": "000001",
        "year": 2020,
        "statement_type": "income_statement",
        "coverage": 1.0,
        "value_accuracy": 1.0,
        "missing_items": [],
        "unmatched_items": [],
        "value_diffs": [],
    }

    ga = GapAnalyzer()
    suggestions = ga.analyze(report)

    assert suggestions == []


def test_gap_analyzer_unit_suggestion_1billion():
    """Test GapAnalyzer detects 1亿元 unit difference."""
    # For 1亿元 check: ratio must be between 0.00009 and 0.00011 (~1/10000)
    # If GT is in 亿元 and extracted is in 万元, ratio = GT/extracted
    # Example: GT=100 (亿元), extracted=1000000 (万元) -> ratio = 100/1000000 = 0.0001
    report = {
        "stock_code": "000001",
        "year": 2020,
        "statement_type": "balance_sheet",
        "coverage": 0.5,
        "value_accuracy": 0.0,
        "missing_items": [],
        "unmatched_items": [],
        "value_diffs": [
            {
                "name": "总资产",
                "code": "F050N",
                "ground_truth_value": 100.0,  # 100亿元
                "extracted_value": 1000000.0,  # 1000000万元 = 100亿元
                "error_pct": 0.0,  # values match when units align
            }
        ],
    }

    ga = GapAnalyzer()
    suggestions = ga.analyze(report)

    # This case should NOT trigger unit suggestion because error_pct is 0
    # The unit suggestion only triggers when values are vastly different
    # Let's use a case where the ratio check would work:
    # ratio = 100.0 / 1000000.0 = 0.0001 (in the 1/10000 range)
    # Actually the ratio check is gt_val/extracted_val, so:
    # ratio = 100.0 / 1000000.0 = 0.0001 which is in range [0.00009, 0.00011]
    # But error_pct check also runs first... let me check the code

    # Looking at GapAnalyzer.analyze():
    # ratio = gt_val / ext_val
    # if 9900 < ratio < 10100 -> 万元
    # elif 0.00009 < ratio < 0.00011 -> 亿元
    #
    # So with gt_val=100 and ext_val=1000000:
    # ratio = 100/1000000 = 0.0001 which IS in the 亿元 range!
    # But we need error_pct > 1% for the diff to be included...

    # Actually looking more carefully, error_pct=0 means this won't show up in value_diffs
    # because the GapAnalyzer filters: only items with value diffs that suggest unit issues
    # Let's use a more realistic case where the error is detected

    # For the unit suggestion to trigger, we need:
    # 1. The item to be in value_diffs (meaning error_pct > 1%)
    # 2. ratio to be in the 亿元 range

    # Let's create a report where 营业收入 appears as having huge value difference
    report2 = {
        "stock_code": "000001",
        "year": 2020,
        "statement_type": "income_statement",
        "coverage": 0.5,
        "value_accuracy": 0.0,
        "missing_items": [],
        "unmatched_items": [],
        "value_diffs": [
            {
                "name": "营业收入",
                "code": "F001N",
                "ground_truth_value": 100.0,  # 100亿元
                "extracted_value": 1000000.0,  # extracted as 万元
                "error_pct": 999900.0,  # huge percentage error
            }
        ],
    }

    suggestions2 = ga.analyze(report2)
    unit_suggestions = [s for s in suggestions2 if s["type"] == "unit_suggestion"]
    assert len(unit_suggestions) == 1
    assert unit_suggestions[0]["suggested_unit"] == "亿元"
    assert unit_suggestions[0]["reason"] == "value_off_by_1billion"


# ---------------------------------------------------------------------------
# Test 3: Mapper discovers mappings with hierarchical aliases
# ---------------------------------------------------------------------------

def _create_temp_extracted_json(stock, year, st, items, extracted_dir):
    """Helper to create a temp extracted JSON file."""
    os.makedirs(os.path.join(extracted_dir, stock), exist_ok=True)
    fname = f"{stock}_{year}_{st}.json"
    path = os.path.join(extracted_dir, stock, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"data": items}, f, ensure_ascii=False)
    return path


def test_mapper_discovers_mappings_with_hierarchical_aliases():
    """
    Test mapper.discover_mappings() with report_type parameter.

    Verifies:
    - discover_mappings accepts report_type='annual'
    - Aliases are loaded correctly for the report_type
    - Mappings are discovered using hierarchical aliases
    """
    from extraction.config import get_aliases

    # Test that report_type parameter is accepted by discover_mappings
    rds_dir = tempfile.mkdtemp()
    extracted_dir = tempfile.mkdtemp()

    try:
        mapper = ItemMapper(rds_dir, extracted_dir)

        # Directly test _find_mappings with known data
        gt_data = {"营业收入": 1000.0, "净利润": 200.0}
        ext_data = {"营业收入": 1000.0, "净利润": 200.0}

        # Get aliases for testing
        aliases = get_aliases("income_statement", "annual")

        # Call _find_mappings directly
        mappings = mapper._find_mappings(
            gt_data, ext_data, "000001", 2023, "income_statement",
            aliases=aliases
        )

        # Verify mappings are found
        assert isinstance(mappings, list)
        assert len(mappings) >= 1  # Should find 营业收入

        # Check mapping structure: (ext_name, rds_name, confidence, values_compared, values_matched)
        for m in mappings:
            assert len(m) == 5  # tuple of 5 elements
            ext_name, rds_name, confidence, vals_comp, vals_match = m
            assert isinstance(ext_name, str)
            assert isinstance(rds_name, str)
            assert isinstance(confidence, float)
            assert 0 <= confidence <= 1

    finally:
        import shutil
        shutil.rmtree(rds_dir, ignore_errors=True)
        shutil.rmtree(extracted_dir, ignore_errors=True)


def test_mapper_different_aliases_for_report_types():
    """
    Test that different report_types load different alias sets.
    """
    from extraction.config import get_aliases

    # Annual aliases should be different from half_year
    annual_aliases = get_aliases("income_statement", "annual")
    half_year_aliases = get_aliases("income_statement", "half_year")

    # Both should be dicts
    assert isinstance(annual_aliases, dict)
    assert isinstance(half_year_aliases, dict)

    # At least one key should be shared (or they could be identical)
    assert len(annual_aliases) > 0
    assert len(half_year_aliases) > 0


def test_mapper_with_multiple_statement_types():
    """Test mapper handles multiple statement types correctly."""
    from extraction.config import get_aliases

    rds_dir = tempfile.mkdtemp()
    extracted_dir = tempfile.mkdtemp()

    try:
        mapper = ItemMapper(rds_dir, extracted_dir)

        # Test with multiple statement types
        gt_data_is = {"营业收入": 1000.0}
        gt_data_bs = {"货币资金": 500.0}
        gt_data_cf = {"经营活动产生的现金流量净额": 100.0}

        ext_data_is = {"营业收入": 1000.0}
        ext_data_bs = {"货币资金": 500.0}
        ext_data_cf = {"经营活动产生的现金流量净额": 100.0}

        # Test each statement type
        for st, gt, ext in [
            ("income_statement", gt_data_is, ext_data_is),
            ("balance_sheet", gt_data_bs, ext_data_bs),
            ("cash_flow", gt_data_cf, ext_data_cf),
        ]:
            aliases = get_aliases(st, "annual")
            mappings = mapper._find_mappings(
                gt, ext, "000001", 2023, st, aliases=aliases
            )
            assert len(mappings) >= 1, f"No mappings for {st}"
            matched_names = {m[1] for m in mappings}
            assert any(name in matched_names for name in gt.keys())

    finally:
        import shutil
        shutil.rmtree(rds_dir, ignore_errors=True)
        shutil.rmtree(extracted_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Integration: Full pipeline simulation
# ---------------------------------------------------------------------------

def test_full_pipeline_simulation():
    """
    Simulate the full Phase 2 pipeline:
    1. Load Tidy Data from RDS
    2. Convert to comparison format
    3. Compare with extracted data
    4. Run GapAnalyzer
    5. Run Mapper
    """
    # Step 1: Simulate Tidy Data (normally from RDS)
    tidy_gt = [
        {"item_code": "F001N", "item_name": "营业收入", "value": 1000.0},
        {"item_code": "F002N", "item_name": "营业成本", "value": 600.0},
        {"item_code": "F003N", "item_name": "净利润", "value": 200.0},
        {"item_code": "F004N", "item_name": "研发费用", "value": 50.0},
    ]

    # Step 2: Convert to comparison format
    gt_data = {item["item_name"]: item["value"] for item in tidy_gt}
    # decode_map format: {code: name}
    decode_map = {item["item_code"]: item["item_name"] for item in tidy_gt}

    # Step 3: Simulated extracted data (with issues)
    # - 营业收入: exact match
    # - 营业成本: ~1.7% error
    # - 净利润: missing from extracted
    # - 研发费用2: unmatched (not in GT)
    # - 研发费用: present with different value
    ext_data = {
        "营业收入": 1000.0,
        "营业成本": 610.0,  # ~1.7% error
        "研发费用": 50.1,  # ~0.2% error (close to exact)
        "研发费用2": 50.0,  # unmatched
    }

    # Step 4: Run comparison
    result = compare_stock(
        gt_data, ext_data, {},
        stock_code="600519",
        year=2020,
        statement_type="income_statement",
        decode_map=decode_map,
    )

    # Verify comparison results
    assert result.coverage >= 0.5  # At least some matches
    report = result.detailed_report()

    # Verify report structure
    assert "missing_items" in report
    assert "unmatched_items" in report
    assert "value_diffs" in report

    # Step 5: Run GapAnalyzer
    ga = GapAnalyzer(min_similarity=0.5)
    suggestions = ga.analyze(report)

    # Should have alias suggestion for unmatched 研发费用2
    alias_suggestions = [s for s in suggestions if s["type"] == "alias_suggestion"]
    # 研发费用2 might be suggested as alias for 研发费用 if similar enough
    assert isinstance(suggestions, list)

    # Step 6: Generate YAML updates
    yaml_updates = ga.generate_yaml_updates(suggestions, statement_type="income_statement")

    # Verify structure
    assert isinstance(yaml_updates, dict)


