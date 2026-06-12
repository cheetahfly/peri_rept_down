# -*- coding: utf-8 -*-
"""tri_channel_cf_lib 单元测试（mock TushareProvider）"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "scripts")
from tri_channel_cf_lib import extract_tushare_year_values, tri_match  # noqa: E402
import tri_channel_cf_download  # noqa: E402


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


def test_tri_match_against_rds_standard():
    """tri_match 对每个 RDS 项找 tushare 中最佳匹配"""
    rds_standard = {
        "净利润": 1_000_000.0,
        "资产总计": 5_000_000.0,
    }
    tushare_values = {
        "[income_statement] n_income": 1_000_000.0,  # exact match
        "[balance_sheet] total_assets": 5_000_500.0,  # close match
        "[cash_flow] c_fr_sale_sg": 800.0,  # not in RDS
    }
    rows = tri_match(tushare_values, rds_standard)
    assert len(rows) == len(rds_standard)
    # 至少一个 exact
    classes = [r["class"] for r in rows]
    assert "exact" in classes


def test_tri_match_handles_no_match():
    """RDS 有但 tushare 完全无候选时标 no_match"""
    rds = {"x_special_item": 999.0}
    tushare = {}  # 完全空 tushare
    rows = tri_match(tushare, rds)
    no_match_rows = [r for r in rows if r["class"] == "no_match"]
    assert len(no_match_rows) >= 1


def test_load_rds_standard_uses_rds_loader():
    """load_rds_standard 调用 RdsLoader.load_stock_data_tidy"""
    with patch.object(tri_channel_cf_download, "RdsLoader") as mock_cls:
        mock_loader = MagicMock()
        mock_loader.load_stock_data_tidy.return_value = [
            {"item_name": "净利润", "value": 100.0, "report_type": "annual"},
            {"item_name": "其他项", "value": 50.0, "report_type": "annual"},
        ]
        mock_cls.return_value = mock_loader

        result = tri_channel_cf_download.load_rds_standard("600519", 2020)

    assert mock_loader.load_stock_data_tidy.call_count == 3
    assert any("balance_sheet" in k.lower() for k in result)
    assert any("income_statement" in k.lower() for k in result)
    assert any("cash_flow" in k.lower() for k in result)
    income_keys = [k for k in result if "income_statement" in k and "净利润" in k]
    assert len(income_keys) == 1
    assert result[income_keys[0]] == 100.0


def test_process_stock_returns_status_dict():
    """process_stock 返回 status dict 包含 counts 与 status 字段"""
    with patch.object(tri_channel_cf_download, "TushareProvider") as mock_ts_cls, \
         patch.object(tri_channel_cf_download, "RdsLoader") as mock_rds_cls:
        mock_ts = MagicMock()
        mock_ts.get_balance_sheet.return_value = {"total_assets": 100.0}
        mock_ts.get_income_statement.return_value = {"total_revenue": 200.0}
        mock_ts.get_cash_flow.return_value = {}
        mock_ts_cls.return_value = mock_ts

        mock_rds = MagicMock()
        mock_rds.load_stock_data_tidy.return_value = [
            {"item_name": "净利润", "value": 200.0, "report_type": "annual"},
        ]
        mock_rds_cls.return_value = mock_rds

        with patch.object(tri_channel_cf_download, "build_merged_csv"), \
             patch.object(tri_channel_cf_download, "build_report_html"):
            result = tri_channel_cf_download.process_stock("600519", 2020, token="fake")

    assert result["stock"] == "600519"
    assert result["year"] == 2020
    assert result["status"] == "OK"
    assert "counts" in result


def test_build_report_html_contains_double_warnings():
    """build_report_html 应含双层警告横幅"""
    import tempfile
    rows = [{"rds_name": "净利润", "rds_value": 100.0, "tushare_label": "x",
             "tushare_value": 100.0, "abs_diff": 0.0, "rel_err_pct": 0.0,
             "class": "exact", "color": "green"}]
    tushare_values = {"[income_statement] x": 100.0}
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        path = f.name
    try:
        tri_channel_cf_download.build_report_html("600519", 2020, rows, tushare_values, path)
        with open(path, encoding="utf-8") as f:
            html = f.read()
        assert "警告 1" in html
        assert "警告 2" in html
        assert "exact" in html
    finally:
        os.unlink(path)
