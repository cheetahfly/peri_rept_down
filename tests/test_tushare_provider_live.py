# -*- coding: utf-8 -*-
"""TushareProvider live smoke test（需 TUSHARE_TOKEN 环境变量）

使用方式：
  export TUSHARE_TOKEN=your_token
  pytest tests/test_tushare_provider_live.py -v

无 token 时自动 skip。
"""
import os
import sys

import pytest

sys.path.insert(0, "astock_fundamentals")
from astock_fundamentals.sources.api import TushareProvider


@pytest.mark.skipif(
    not os.environ.get("TUSHARE_TOKEN"),
    reason="TUSHARE_TOKEN not set — skipping live test",
)
def test_live_get_cash_flow_one_stock():
    """live: 1 只股 × 1 年 CF（验证 token 有效 + 字段非空）"""
    token = os.environ["TUSHARE_TOKEN"]
    provider = TushareProvider(token=token)
    result = provider.get_cash_flow("600519", 2020, "annual")
    assert result, "live call returned empty dict"
    assert isinstance(result, dict)
    # 间接法 + 直接法都应有
    assert "net_profit" in result, f"missing net_profit; got {list(result.keys())[:5]}"
    assert "c_fr_sale_sg" in result, f"missing c_fr_sale_sg; got {list(result.keys())[:5]}"
    print(f"\n  Got {len(result)} fields: {list(result.keys())[:5]}")
