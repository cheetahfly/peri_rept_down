# -*- coding: utf-8 -*-
"""
Tushare数据源 - 通过tushare库获取A股财务数据

安装: pip install tushare

Tushare 提供结构化金融数据API（部分数据需积分）。
文档: https://tushare.pro/document/2

源头：Tushare 标榜"巨潮资讯"（cninfo）结构化财报数据，与 RDS 同源。
使用本 provider 后，请运行 scripts/tri_channel_cf_download.py 与 RDS 对比，
验证 exact_rate 假设。
"""
import time
from typing import Dict, Optional

import pandas as pd

from astock_fundamentals.sources.api import BaseApiProvider


class TushareProvider(BaseApiProvider):
    """Tushare 财务数据获取器"""
    name = "tushare"

    def __init__(self, token: str = "", rate_limit_sleep: float = 0.4):
        if not token:
            raise ValueError(
                "TushareProvider 需要 token。请通过 TUSHARE_TOKEN 环境变量或 --token 参数提供。"
            )
        self._token = token
        self._api = None
        self._sleep = rate_limit_sleep
        self._last_call_ts = 0.0

    def _connect(self):
        if self._api is not None:
            return
        try:
            import tushare as ts
            ts.set_token(self._token)
            self._api = ts.pro_api()
        except ImportError:
            raise ImportError("请安装 tushare: pip install tushare")

    def _throttle(self):
        """强制 sleep 间隔，避免触发 200 req/min 限流"""
        elapsed = time.time() - self._last_call_ts
        if elapsed < self._sleep:
            time.sleep(self._sleep - elapsed)
        self._last_call_ts = time.time()

    # _fetch / _df_to_dict / _ts_code / _period
    # 在 Task 2.3-2.4 中实现
    # get_*_statement 在 Task 2.5-2.7 中实现
