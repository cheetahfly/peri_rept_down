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
