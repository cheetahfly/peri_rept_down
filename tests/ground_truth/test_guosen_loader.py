import os
import sys
import pytest

import pandas as pd  # noqa: E402

# Ensure project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from astock_fundamentals.sources.guosen import (
    GuosenLoader,
    GuosenAuthError,
    GuosenEmptyDataError,
)


def test_guosen_auth_error_is_exception():
    assert issubclass(GuosenAuthError, Exception)


def test_guosen_empty_data_error_is_exception():
    assert issubclass(GuosenEmptyDataError, Exception)


def test_guosen_load_raises_auth_error_when_no_key(monkeypatch):
    monkeypatch.delenv("GS_API_KEY", raising=False)
    with pytest.raises(GuosenAuthError):
        GuosenLoader()


def test_guosen_load_uses_explicit_api_key():
    loader = GuosenLoader(api_key="explicit-test-key")
    assert loader.api_key == "explicit-test-key"


def test_guosen_load_uses_env_var(monkeypatch):
    monkeypatch.setenv("GS_API_KEY", "env-test-key")
    loader = GuosenLoader()
    assert loader.api_key == "env-test-key"


def test_guosen_load_reads_memory_md(monkeypatch, tmp_path):
    monkeypatch.delenv("GS_API_KEY", raising=False)
    memory_path = tmp_path / "memory.md"
    memory_path.write_text("# Project memory\nGS_API_KEY=memory-test-key\n")
    loader = GuosenLoader(memory_path=str(memory_path))
    assert loader.api_key == "memory-test-key"


def _make_api_response(items):
    """Build a fake guosen API response.

    The API data rows have field names as column keys (from info[*].name),
    not a generic "value" key. e.g. {"date": "2019-12-31", "货币资金": 1000000.0, ...}
    """
    info = [{"key": item["key"], "name": item["name"]} for item in items]
    # Group items by date - each date is one row
    date_to_values: dict = {}
    for item in items:
        d = item["date"]
        if d not in date_to_values:
            date_to_values[d] = {}
        date_to_values[d][item["name"]] = item["value"]
    data_list = [{"date": d, **vals} for d, vals in sorted(date_to_values.items())]
    return {
        "result": {"code": 0, "msg": "请求成功"},
        "data": {"info": info, "data": data_list},
    }


def test_guosen_read_statement_returns_dataframe():
    """read_statement should return a DataFrame with Chinese column names."""
    items = [
        {"key": "F006N", "name": "货币资金", "date": "2019-12-31", "value": 1000000.0},
        {"key": "F077N", "name": "结算备付金", "date": "2019-12-31", "value": 500000.0},
    ]

    def fake_query(code, market, report_type="Q0", report_year=None, count=1):
        return _make_api_response(items)

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_a_stock_balance_sheet"] = fake_query
    df = loader.read_statement("600519", "balance_sheet")
    assert isinstance(df, pd.DataFrame)
    assert "报告日" in df.columns
    assert len(df) == 1
    # Chinese field names should be columns
    assert "货币资金" in df.columns
    assert "结算备付金" in df.columns


def test_guosen_read_statement_detects_market_by_prefix():
    """600xxx should be SH, 000xxx should be SZ."""
    captured = {}

    def fake_query(code, market, report_type="Q0", report_year=None, count=1):
        captured["code"] = code
        captured["market"] = market
        return _make_api_response([])

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_a_stock_balance_sheet"] = fake_query
    loader.read_statement("600519", "balance_sheet")
    assert captured["market"] == "SH"

    loader.read_statement("000001", "balance_sheet")
    assert captured["market"] == "SZ"


def test_guosen_read_statement_handles_hk_stock():
    """5-digit HK code should be passed with market=HK."""
    captured = {}

    def fake_query(code, report_year=None, report_type=None, count=1):
        captured["code"] = code
        captured["market"] = "HK"
        return _make_api_response([])

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_hk_stock_balance_sheet"] = fake_query
    df = loader.read_statement("02020", "balance_sheet")
    assert captured["code"] == "02020"


def test_guosen_read_statement_raises_on_error():
    def fake_query(*args, **kwargs):
        return {"result": {"code": -1, "msg": "API key 无效"}}

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_a_stock_balance_sheet"] = fake_query
    with pytest.raises(Exception) as excinfo:
        loader.read_statement("600519", "balance_sheet")
    assert "API key 无效" in str(excinfo.value) or "error" in str(excinfo.value).lower()


def test_guosen_get_annual_filters_to_target_years():
    """get_annual should filter API response to 2019-2022 only."""
    items = [
        {"key": "F006N", "name": "货币资金", "date": "2018-12-31", "value": 1.0},
        {"key": "F006N", "name": "货币资金", "date": "2019-12-31", "value": 2.0},
        {"key": "F006N", "name": "货币资金", "date": "2020-12-31", "value": 3.0},
        {"key": "F006N", "name": "货币资金", "date": "2021-12-31", "value": 4.0},
        {"key": "F006N", "name": "货币资金", "date": "2022-12-31", "value": 5.0},
        {"key": "F006N", "name": "货币资金", "date": "2023-12-31", "value": 6.0},
    ]

    def fake_query(code, market, report_type="Q0", report_year=None, count=1):
        return _make_api_response(items)

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_a_stock_balance_sheet"] = fake_query
    df = loader.get_annual("600519", [2019, 2020, 2021, 2022], "balance_sheet")
    assert len(df) == 4
    # 报告日 should be 2019..2022 only
    periods = set(df["报告日"].astype(str))
    assert periods == {"2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31"}
    assert df["货币资金"].tolist() == [2.0, 3.0, 4.0, 5.0]


def test_guosen_get_annual_passes_count_to_api():
    """get_annual should pass count = max(target_years) - min(target_years) + 1."""
    captured = {}

    def fake_query(code, market, report_type="Q0", report_year=None, count=1):
        captured["count"] = count
        return _make_api_response([])

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_a_stock_balance_sheet"] = fake_query
    loader.get_annual("600519", [2019, 2020, 2021, 2022], "balance_sheet")
    assert captured["count"] == 4  # 4 years requested