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

    @staticmethod
    def _ts_code(stock_code: str) -> str:
        """600xxx → 600xxx.SH, 0xxxxx/3xxxxx → 0xxxxx.SZ"""
        if stock_code.startswith(("600", "601", "603", "605", "688")):
            return f"{stock_code}.SH"
        if stock_code.startswith(("000", "001", "002", "003", "300", "301")):
            return f"{stock_code}.SZ"
        raise ValueError(f"Unknown market for stock code: {stock_code}")

    # _fetch / _df_to_dict
    # _fetch 在 Task 2.4 中实现，_df_to_dict 在 Task 2.5 中实现
    # get_*_statement 在 Task 2.5-2.7 中实现

    def _fetch(self, api_name: str, **kwargs) -> pd.DataFrame:
        """统一调用入口：throttle + 3 次指数退避（不重试权限错误）"""
        self._connect()
        self._throttle()
        for attempt in range(3):
            try:
                return getattr(self._api, api_name)(**kwargs)
            except Exception as e:
                err_msg = str(e)
                # 权限/积分错误不重试
                if "权限" in err_msg or "积分" in err_msg or "token" in err_msg.lower():
                    raise
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        return pd.DataFrame()  # 不应到达此处

    # tushare 返回字段中需要排除的元数据列
    _META_COLUMNS = {
        "ts_code", "end_date", "ann_date", "f_ann_date", "update_flag",
    }

    def _df_to_dict(self, df: pd.DataFrame) -> Dict[str, float]:
        """DataFrame → {item_name: value}，排除元数据列"""
        if df is None or df.empty:
            return {}
        result = {}
        for col in df.columns:
            if col in self._META_COLUMNS:
                continue
            val = df[col].iloc[0] if len(df) > 0 else None
            if pd.notna(val) and isinstance(val, (int, float)):
                result[col] = float(val)
        return result

    @staticmethod
    def _period(year: int, report_type: str) -> str:
        """年份 + 报告期 → tushare 周期字符串（YYYYMMDD）"""
        period_map = {
            "annual": "1231",
            "half": "0630",
            "q1": "0331",
            "q3": "0930",
        }
        suffix = period_map.get(report_type)
        if suffix is None:
            raise ValueError(f"Unknown report_type: {report_type}")
        return f"{year}{suffix}"
