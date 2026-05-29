# -*- coding: utf-8 -*-
"""
Wind数据源 - 通过Wind接口获取A股财务数据

需安装Wind终端和Wind Python接口（由Wind终端提供）。
文档: https://www.wind.com.cn/
"""
from typing import Dict, Optional

from astock_fundamentals.sources.api import BaseApiProvider


class WindProvider(BaseApiProvider):
    """Wind 财务数据获取器"""
    name = "wind"

    def __init__(self):
        self._wss = None

    def _connect(self):
        if self._wss is not None:
            return
        try:
            from WindPy import w
            w.start()
            self._wss = w
        except ImportError:
            raise ImportError("Wind接口未安装，请确认Wind终端已安装并配置Python接口")

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
