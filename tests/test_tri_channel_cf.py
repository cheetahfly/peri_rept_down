# -*- coding: utf-8 -*-
"""tri_channel_cf_lib 单元测试（mock TushareProvider）"""
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, "scripts")
from tri_channel_cf_lib import extract_tushare_year_values  # noqa: E402


def test_extract_tushare_year_values_combines_three_statements():
    """extract 应调 provider 的 3 个 get_*，返回带表名前缀的 dict"""
    mock_provider = MagicMock()
    mock_provider.get_balance_sheet.return_value = {"total_assets": 100.0}
    mock_provider.get_income_statement.return_value = {"total_revenue": 500.0}
    mock_provider.get_cash_flow.return_value = {"c_fr_sale_sg": 300.0}

    result = extract_tushare_year_values(mock_provider, "600519", 2020)

    # 应包含 3 个 statement 的 key
    assert any("balance_sheet" in k for k in result)
    assert any("income_statement" in k for k in result)
    assert any("cash_flow" in k for k in result)
    # 值正确
    assert result["[balance_sheet] total_assets"] == 100.0
    assert result["[income_statement] total_revenue"] == 500.0
    assert result["[cash_flow] c_fr_sale_sg"] == 300.0
    # 调了 3 次
    mock_provider.get_balance_sheet.assert_called_once_with("600519", 2020)
    mock_provider.get_income_statement.assert_called_once_with("600519", 2020)
    mock_provider.get_cash_flow.assert_called_once_with("600519", 2020)


def test_extract_tushare_skips_empty_statements():
    """空 dict 语句应被跳过（不报异常）"""
    mock_provider = MagicMock()
    mock_provider.get_balance_sheet.return_value = None
    mock_provider.get_income_statement.return_value = {}
    mock_provider.get_cash_flow.return_value = {"x": 1.0}

    result = extract_tushare_year_values(mock_provider, "600519", 2020)
    assert "[cash_flow] x" in result
    assert len([k for k in result if "balance_sheet" in k]) == 0
