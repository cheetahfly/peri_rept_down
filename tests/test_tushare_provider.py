# -*- coding: utf-8 -*-
"""TushareProvider 单元测试（mock tushare 库，无 token 依赖）"""
import sys
import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, "astock_fundamentals")
sys.path.insert(0, "scripts")

from astock_fundamentals.sources.api.tushare_provider import TushareProvider


@pytest.fixture
def fake_tushare():
    """Patch tushare 模块以避免 import 错误"""
    fake = MagicMock()
    fake.set_token = MagicMock()
    fake.pro_api = MagicMock(return_value=MagicMock())
    sys.modules["tushare"] = fake
    yield fake
    del sys.modules["tushare"]


@pytest.fixture
def provider(fake_tushare):
    return TushareProvider(token="fake", rate_limit_sleep=0.1)


def test_throttle_sleeps_when_too_fast(provider):
    """_throttle 应该在两次连续调用之间 sleep"""
    provider._last_call_ts = time.time()  # 上次调用刚刚发生
    start = time.time()
    provider._throttle()
    elapsed = time.time() - start
    # 至少 sleep 0.05s（rate_limit_sleep=0.1，留 50% 余量）
    assert elapsed >= 0.05, f"throttle too fast: {elapsed}s"


def test_throttle_skips_when_enough_time_passed(provider):
    """_throttle 在间隔足够时不应 sleep"""
    provider._last_call_ts = time.time() - 1.0  # 1 秒前
    start = time.time()
    provider._throttle()
    elapsed = time.time() - start
    # 不应 sleep
    assert elapsed < 0.05, f"throttle unexpectedly slow: {elapsed}s"


def test_ts_code_sh_prefix():
    """6xx 开头的股票加 .SH 后缀"""
    p = TushareProvider.__new__(TushareProvider)  # 不触发 token 检查
    assert p._ts_code("600519") == "600519.SH"
    assert p._ts_code("601318") == "601318.SH"
    assert p._ts_code("688981") == "688981.SH"


def test_ts_code_sz_prefix():
    """0xx/3xx 开头的股票加 .SZ 后缀"""
    p = TushareProvider.__new__(TushareProvider)
    assert p._ts_code("000001") == "000001.SZ"
    assert p._ts_code("300750") == "300750.SZ"
    assert p._ts_code("002415") == "002415.SZ"


def test_ts_code_unknown_market_raises():
    """未知前缀应抛 ValueError"""
    p = TushareProvider.__new__(TushareProvider)
    with pytest.raises(ValueError, match="Unknown market"):
        p._ts_code("999999")


def test_period_annual():
    p = TushareProvider.__new__(TushareProvider)
    assert p._period(2020, "annual") == "20201231"


def test_period_half():
    p = TushareProvider.__new__(TushareProvider)
    assert p._period(2020, "half") == "20200630"


def test_period_q1():
    p = TushareProvider.__new__(TushareProvider)
    assert p._period(2020, "q1") == "20200331"


def test_period_q3():
    p = TushareProvider.__new__(TushareProvider)
    assert p._period(2020, "q3") == "20200930"


def test_fetch_calls_throttle_and_returns_df(provider):
    """_fetch 调用前 throttle，调用后返回 DataFrame"""
    fake_df = pd.DataFrame({"a": [1, 2]})
    provider._api = MagicMock()
    provider._api.test_endpoint = MagicMock(return_value=fake_df)

    result = provider._fetch("test_endpoint", x=1)
    assert result.equals(fake_df)
    provider._api.test_endpoint.assert_called_once_with(x=1)


def test_fetch_retries_on_network_error_then_succeeds(provider):
    """网络错误指数退避，最终成功"""
    fake_df = pd.DataFrame({"a": [1]})
    provider._api = MagicMock()
    provider._api.test_endpoint = MagicMock(side_effect=[
        ConnectionError("net"),
        ConnectionError("net"),
        fake_df,
    ])
    result = provider._fetch("test_endpoint", x=1)
    assert result.equals(fake_df)
    assert provider._api.test_endpoint.call_count == 3


def test_fetch_does_not_retry_on_permission_error(provider):
    """权限错误不重试，立即抛"""
    provider._api = MagicMock()
    provider._api.test_endpoint = MagicMock(side_effect=Exception("积分不足"))
    with pytest.raises(Exception, match="积分不足"):
        provider._fetch("test_endpoint", x=1)
    assert provider._api.test_endpoint.call_count == 1


def test_df_to_dict_basic(provider):
    """标准 tushare 返回 → {item_name: value}"""
    df = pd.DataFrame({
        "ts_code": ["600519.SH"],
        "end_date": ["20201231"],
        "total_assets": [1000000.0],
        "total_liab": [400000.0],
    })
    result = provider._df_to_dict(df)
    # 包含 financial items
    assert result["total_assets"] == 1000000.0
    assert result["total_liab"] == 400000.0
    # metadata 列被排除
    assert "ts_code" not in result
    assert "end_date" not in result


def test_df_to_dict_empty(provider):
    """空 DataFrame → 空 dict"""
    assert provider._df_to_dict(pd.DataFrame()) == {}


def test_df_to_dict_nan_excluded(provider):
    """NaN 值应被排除"""
    df = pd.DataFrame({"total_assets": [float("nan")], "revenue": [100.0]})
    result = provider._df_to_dict(df)
    assert "total_assets" not in result
    assert result["revenue"] == 100.0


def test_get_balance_sheet_calls_balancesheet_endpoint(provider):
    """get_balance_sheet 应调 tushare 的 balancesheet 接口"""
    fake_df = pd.DataFrame({"total_assets": [100.0]})
    provider._api = MagicMock()
    provider._api.balancesheet = MagicMock(return_value=fake_df)
    result = provider.get_balance_sheet("600519", 2020, "annual")
    assert result == {"total_assets": 100.0}
    call_kwargs = provider._api.balancesheet.call_args.kwargs
    assert call_kwargs["ts_code"] == "600519.SH"
    assert call_kwargs["period"] == "20201231"
    assert call_kwargs["report_type"] == "annual"


def test_get_income_statement_calls_income_endpoint(provider):
    fake_df = pd.DataFrame({"total_revenue": [500.0]})
    provider._api = MagicMock()
    provider._api.income = MagicMock(return_value=fake_df)
    result = provider.get_income_statement("000001", 2021, "half")
    assert result == {"total_revenue": 500.0}
    call_kwargs = provider._api.income.call_args.kwargs
    assert call_kwargs["ts_code"] == "000001.SZ"
    assert call_kwargs["period"] == "20210630"


def test_get_cash_flow_calls_cashflow_endpoint(provider):
    fake_df = pd.DataFrame({"c_fr_sale_sg": [800.0]})
    provider._api = MagicMock()
    provider._api.cashflow = MagicMock(return_value=fake_df)
    result = provider.get_cash_flow("300750", 2022, "q3")
    assert result == {"c_fr_sale_sg": 800.0}
    call_kwargs = provider._api.cashflow.call_args.kwargs
    assert call_kwargs["ts_code"] == "300750.SZ"
    assert call_kwargs["period"] == "20220930"


def test_get_balance_sheet_empty_returns_empty_dict(provider):
    """空 DataFrame（报告期未发布）→ 空 dict"""
    provider._api = MagicMock()
    provider._api.balancesheet = MagicMock(return_value=pd.DataFrame())
    assert provider.get_balance_sheet("688981", 2018, "annual") == {}
