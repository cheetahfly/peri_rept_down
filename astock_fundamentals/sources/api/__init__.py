# -*- coding: utf-8 -*-
"""
API数据源 - 通过第三方库获取A股财务数据

各API均为独立子模块，可按需安装依赖：
  pip install akshare     # akshare 数据源
  pip install tushare     # Tushare 数据源
  # Wind 需从Wind终端安装

用法:
    from astock_fundamentals.sources.api import AKShareProvider
    provider = AKShareProvider()
    data = provider.get_balance_sheet("600519", 2020)
"""
from typing import Dict, List, Optional


class BaseApiProvider:
    """API数据源基类 - 定义统一接口"""
    name = "base"

    def get_balance_sheet(self, stock_code: str, year: int, report_type: str = "annual") -> Optional[Dict]:
        raise NotImplementedError

    def get_income_statement(self, stock_code: str, year: int, report_type: str = "annual") -> Optional[Dict]:
        raise NotImplementedError

    def get_cash_flow(self, stock_code: str, year: int, report_type: str = "annual") -> Optional[Dict]:
        raise NotImplementedError
