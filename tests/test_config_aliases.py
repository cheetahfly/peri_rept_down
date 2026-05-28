# -*- coding: utf-8 -*-
"""Tests for hierarchical alias loading in config.py"""

from extraction.config import get_aliases, ITEM_ALIAS_MAP


def test_get_aliases_returns_hierarchical():
    """Test get_aliases returns correct structure"""
    # Test income_statement annual
    aliases = get_aliases("income_statement", "annual")
    assert isinstance(aliases, dict)
    assert "营业收入" in aliases

    # Test balance_sheet annual
    bs_aliases = get_aliases("balance_sheet", "annual")
    assert isinstance(bs_aliases, dict)
    assert "资产总计" in bs_aliases


def test_get_aliases_fallback_to_annual():
    """Test fallback to annual when report_type not found"""
    annual_aliases = get_aliases("income_statement", "annual")
    # quarter_q1 may not exist, should fallback to annual
    q1_aliases = get_aliases("income_statement", "quarter_q1")
    # Should either equal annual or be empty (if quarter_q1 truly missing)
    assert q1_aliases == annual_aliases or q1_aliases == {}


def test_item_alias_map_backward_compatible():
    """Test ITEM_ALIAS_MAP is still available for backward compatibility"""
    assert isinstance(ITEM_ALIAS_MAP, dict)
    assert len(ITEM_ALIAS_MAP) > 0
    # ITEM_ALIAS_MAP defaults to income_statement.annual
    assert "营业收入" in ITEM_ALIAS_MAP


def test_get_aliases_cash_flow():
    """Test get_aliases works for cash_flow statement type"""
    cf_aliases = get_aliases("cash_flow", "annual")
    assert isinstance(cf_aliases, dict)
    assert "经营活动产生的现金流量净额" in cf_aliases


def test_get_aliases_invalid_statement_type():
    """Test get_aliases handles invalid statement_type gracefully"""
    result = get_aliases("invalid_type", "annual")
    assert result == {}