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
