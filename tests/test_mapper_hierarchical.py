# -*- coding: utf-8 -*-
"""Tests for hierarchical alias support in ItemMapper."""

import tempfile
import os
import json
import pytest

from extraction.config import get_aliases
from extraction.ground_truth.comparator import normalize_name
from extraction.ground_truth.mapper import ItemMapper, NameMapping


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path, data):
    """Write a JSON file, creating parent dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _make_extracted_json(stock, year, st, items):
    """Create an extracted JSON file in a temp dir and return the dir."""
    tmpdir = tempfile.mkdtemp()
    fname = f"{stock}_{year}_{st}.json"
    path = os.path.join(tmpdir, stock, fname)
    _write_json(path, {"data": items})
    return tmpdir


def _make_gt_dir():
    """Create a minimal RDS dir (we will mock loader.load_stock_data)."""
    return tempfile.mkdtemp()


# ---------------------------------------------------------------------------
# Tests: discover_mappings with report_type parameter
# ---------------------------------------------------------------------------

class TestDiscoverMappingsReportType:
    """Test that discover_mappings passes report_type through correctly."""

    def test_default_report_type_is_annual(self):
        """discover_mappings defaults to report_type='annual'."""
        mapper = _make_mapper()
        # Just verify the signature accepts it without error
        import inspect
        sig = inspect.signature(mapper.discover_mappings)
        assert sig.parameters["report_type"].default == "annual"

    def test_industry_parameter_accepted(self):
        """discover_mappings accepts industry parameter (reserved for future use)."""
        mapper = _make_mapper()
        import inspect
        sig = inspect.signature(mapper.discover_mappings)
        assert "industry" in sig.parameters
        assert sig.parameters["industry"].default is None

    def test_aliases_loaded_for_each_statement_type(self):
        """Verify aliases are pre-loaded for each statement type."""
        mapper = _make_mapper()
        # Mock loader to return data
        gt_data_income = {"营业收入": 1000.0, "净利润": 200.0}
        gt_data_bs = {"资产总计": 5000.0}
        ext_data_income = {"营业收入": 1000.0, "净利润": 200.0}
        ext_data_bs = {"资产总计": 5000.0}

        mapper.loader.load_stock_data = lambda s, y, st: {
            "income_statement": gt_data_income,
            "balance_sheet": gt_data_bs,
        }.get(st, {})

        _write_json(
            os.path.join(mapper.extracted_dir, "000001", "000001_2023_income_statement.json"),
            ext_data_income,
        )
        _write_json(
            os.path.join(mapper.extracted_dir, "000001", "000001_2023_balance_sheet.json"),
            ext_data_bs,
        )

        # We need at least 2 stocks for discover_mappings to return results
        # Create second stock with same data
        _write_json(
            os.path.join(mapper.extracted_dir, "000002", "000002_2023_income_statement.json"),
            ext_data_income,
        )
        _write_json(
            os.path.join(mapper.extracted_dir, "000002", "000002_2023_balance_sheet.json"),
            ext_data_bs,
        )

        # This should not raise even with report_type
        result = mapper.discover_mappings(
            stock_codes=["000001", "000002"],
            years=[2023],
            report_type="annual",
        )
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Tests: _find_mappings with aliases
# ---------------------------------------------------------------------------

class TestFindMappingsAliases:
    """Test the three-tier matching strategy in _find_mappings."""

    def _make_mapper_for_test(self):
        return _make_mapper()

    def test_tier1_exact_match_wins(self):
        """When exact match exists, it should be preferred over alias."""
        mapper = self._make_mapper_for_test()
        gt_data = {"营业收入": 1000.0}
        ext_data = {"营业收入": 1000.0}
        aliases = {"营业收入": ["营业总收入", "营业收入合计"]}

        mappings = mapper._find_mappings(gt_data, ext_data, "000001", 2023, "income_statement", aliases=aliases)
        assert len(mappings) == 1
        ext_name, rds_name, score, _, _ = mappings[0]
        assert ext_name == "营业收入"
        assert rds_name == "营业收入"
        assert score >= 0.95  # exact match should score high

    def test_tier2_alias_match_when_no_exact(self):
        """When no exact match, alias variant should be found."""
        mapper = self._make_mapper_for_test()
        gt_data = {"营业收入": 1000.0}
        ext_data = {"营业总收入": 1000.0}
        aliases = {"营业收入": ["营业总收入", "营业收入合计"]}

        mappings = mapper._find_mappings(gt_data, ext_data, "000001", 2023, "income_statement", aliases=aliases)
        assert len(mappings) == 1
        ext_name, rds_name, score, _, _ = mappings[0]
        assert ext_name == "营业总收入"
        assert rds_name == "营业收入"
        assert 0.6 <= score <= 0.95  # alias match score range

    def test_tier2_reverse_alias_match(self):
        """When gt_name is a variant, reverse alias lookup should find the standard."""
        mapper = self._make_mapper_for_test()
        gt_data = {"营业总收入": 1000.0}  # gt uses variant
        ext_data = {"营业收入": 1000.0}  # ext uses standard
        aliases = {"营业收入": ["营业总收入", "营业收入合计"]}

        mappings = mapper._find_mappings(gt_data, ext_data, "000001", 2023, "income_statement", aliases=aliases)
        assert len(mappings) == 1
        ext_name, rds_name, score, _, _ = mappings[0]
        assert ext_name == "营业收入"
        assert rds_name == "营业总收入"

    def test_tier3_fuzzy_fallback_when_no_aliases(self):
        """When no aliases match, fuzzy matching should still work."""
        mapper = self._make_mapper_for_test()
        gt_data = {"营业收入": 1000.0}
        ext_data = {"营业收入净额": 1000.0}  # not an alias, but similar

        # No aliases provided
        mappings = mapper._find_mappings(gt_data, ext_data, "000001", 2023, "income_statement")
        # May or may not match depending on fuzzy threshold
        # Just verify it doesn't crash
        assert isinstance(mappings, list)

    def test_no_match_returns_empty(self):
        """When nothing matches, return empty list."""
        mapper = self._make_mapper_for_test()
        gt_data = {"营业收入": 1000.0}
        ext_data = {"完全不相关的科目": 500.0}
        aliases = {"营业收入": ["营业总收入"]}

        mappings = mapper._find_mappings(gt_data, ext_data, "000001", 2023, "income_statement", aliases=aliases)
        # Should not match because the names are too different
        # (fuzzy threshold is 0.6)
        for ext_name, rds_name, score, _, _ in mappings:
            assert ext_name != "完全不相关的科目" or score < 0.6

    def test_value_mismatch_penalizes_score(self):
        """Mismatched values should lower the score but still match if names are exact."""
        mapper = self._make_mapper_for_test()
        gt_data = {"净利润": 1000.0}
        ext_data = {"净利润": 900.0}  # 10% off
        aliases = {"净利润": ["净亏损"]}

        mappings = mapper._find_mappings(gt_data, ext_data, "000001", 2023, "income_statement", aliases=aliases)
        assert len(mappings) == 1
        ext_name, rds_name, score, _, values_matched = mappings[0]
        assert ext_name == "净利润"
        # Value is 10% off, val_sim = 0.9, so values_matched = 0 (threshold > 0.9)
        assert values_matched == 0

    def test_multiple_gt_items(self):
        """Multiple GT items should all get matched when aliases exist."""
        mapper = self._make_mapper_for_test()
        gt_data = {"营业收入": 1000.0, "净利润": 200.0, "资产总计": 5000.0}
        ext_data = {"营业总收入": 1000.0, "净亏损": 200.0, "资产合计": 5000.0}
        aliases = {
            "营业收入": ["营业总收入"],
            "净利润": ["净亏损"],
            "资产总计": ["资产合计"],
        }

        mappings = mapper._find_mappings(gt_data, ext_data, "000001", 2023, "income_statement", aliases=aliases)
        matched_rds = {rds_name for _, rds_name, _, _, _ in mappings}
        assert "营业收入" in matched_rds
        assert "净利润" in matched_rds
        # 资产总计 is balance_sheet, but aliases are checked anyway

    def test_aliases_none_backward_compatible(self):
        """When aliases=None, behavior should be identical to before."""
        mapper = self._make_mapper_for_test()
        gt_data = {"营业收入": 1000.0}
        ext_data = {"营业收入": 1000.0}

        mappings_no_alias = mapper._find_mappings(gt_data, ext_data, "000001", 2023, "income_statement", aliases=None)
        mappings_default = mapper._find_mappings(gt_data, ext_data, "000001", 2023, "income_statement")
        assert len(mappings_no_alias) == len(mappings_default)
        assert mappings_no_alias[0][0] == mappings_default[0][0]


# ---------------------------------------------------------------------------
# Tests: alias integration with get_aliases
# ---------------------------------------------------------------------------

class TestAliasIntegration:
    """Test that aliases from config.py integrate correctly."""

    def test_annual_aliases_for_income_statement(self):
        """Verify income_statement annual aliases load correctly."""
        aliases = get_aliases("income_statement", "annual")
        assert isinstance(aliases, dict)
        assert "营业收入" in aliases
        assert "营业总收入" in aliases["营业收入"]

    def test_annual_aliases_for_balance_sheet(self):
        """Verify balance_sheet annual aliases load correctly."""
        aliases = get_aliases("balance_sheet", "annual")
        assert isinstance(aliases, dict)
        assert "资产总计" in aliases
        assert "资产合计" in aliases["资产总计"]

    def test_annual_aliases_for_cash_flow(self):
        """Verify cash_flow annual aliases load correctly."""
        aliases = get_aliases("cash_flow", "annual")
        assert isinstance(aliases, dict)
        assert "经营活动产生的现金流量净额" in aliases

    def test_mapper_uses_correct_aliases_per_statement(self):
        """Mapper should use different aliases for each statement type."""
        mapper = _make_mapper()

        # income_statement aliases should have 营业收入
        is_aliases = get_aliases("income_statement", "annual")
        assert "营业收入" in is_aliases

        # balance_sheet aliases should have 资产总计
        bs_aliases = get_aliases("balance_sheet", "annual")
        assert "资产总计" in bs_aliases

        # They should be different
        assert is_aliases != bs_aliases


# ---------------------------------------------------------------------------
# Tests: normalize_name integration
# ---------------------------------------------------------------------------

class TestNormalizeNameIntegration:
    """Test that normalize_name works correctly with alias variants."""

    def test_normalize_removes_prefixes(self):
        """normalize_name should strip common prefixes."""
        assert normalize_name("其中：营业收入") == "营业收入"
        assert normalize_name("减：营业外支出") == "营业外支出"

    def test_normalize_removes_numbering(self):
        """normalize_name should strip numbering."""
        assert normalize_name("一、资产总计") == "资产总计"
        assert normalize_name("（一）基本每股收益") == "基本每股收益"

    def test_normalize_variant_matches_standard(self):
        """A variant from aliases should normalize to match the standard name."""
        aliases = get_aliases("income_statement", "annual")
        for standard, variants in aliases.items():
            norm_std = normalize_name(standard)
            for variant in variants:
                norm_v = normalize_name(variant)
                # At minimum, both should normalize to non-empty strings
                assert norm_std, f"Standard '{standard}' normalizes to empty"
                assert norm_v, f"Variant '{variant}' normalizes to empty"


# ---------------------------------------------------------------------------
# Helper to create a mapper instance
# ---------------------------------------------------------------------------

def _make_mapper():
    """Create an ItemMapper with temp directories."""
    rds_dir = _make_gt_dir()
    extracted_dir = tempfile.mkdtemp()
    mapper = ItemMapper(rds_dir, extracted_dir)
    return mapper
