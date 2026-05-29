# -*- coding: utf-8 -*-
"""
Tushare数据源 - 通过tushare库获取A股财务数据

安装: pip install tushare

Tushare 提供结构化金融数据API（部分数据需积分）。
文档: https://tushare.pro/
"""
from typing import Dict, Optional

from astock_fundamentals.sources.api import BaseApiProvider


class TushareProvider(BaseApiProvider):
    """Tushare 财务数据获取器"""
    name = "tushare"

    def __init__(self, token: str = ""):
        self._token = token
        self._api = None

    def _connect(self):
        if self._api is not None:
            return
        try:
            import tushare as ts
            if self._token:
                ts.set_token(self._token)
            self._api = ts.pro_api()
        except ImportError:
            raise ImportError("请安装 tushare: pip install tushare")

    def get_balance_sheet(self, stock_code: str, year: int,
                          report_type: str = "annual") -> Optional[Dict]:
        self._connect()
        # TODO: 实现资产负债表获取
        return None

    def get_income_statement(self, stock_code: str, year: int,
                             report_type: str = "annual") -> Optional[Dict]:
        self._connect()
        return None

    def get_cash_flow(self, stock_code: str, year: int,
                      report_type: str = "annual") -> Optional[Dict]:
        self._connect()
        return None
