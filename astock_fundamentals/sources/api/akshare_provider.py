# -*- coding: utf-8 -*-
"""
AKShare数据源 - 通过akshare库获取A股财务数据

安装: pip install akshare

AKShare 提供免费的中国金融市场数据API，包括上市公司财务报表。
文档: https://akshare.akfamily.xyz/
"""
from typing import Dict, Optional

from astock_fundamentals.sources.api import BaseApiProvider


class AKShareProvider(BaseApiProvider):
    """AKShare 财务数据获取器"""
    name = "akshare"

    def get_balance_sheet(self, stock_code: str, year: int,
                          report_type: str = "annual") -> Optional[Dict]:
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")
        # TODO: 实现资产负债表获取
        # df = ak.stock_financial_report_sina(stock=stock_code, symbol="资产负债表")
        return None

    def get_income_statement(self, stock_code: str, year: int,
                             report_type: str = "annual") -> Optional[Dict]:
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")
        return None

    def get_cash_flow(self, stock_code: str, year: int,
                      report_type: str = "annual") -> Optional[Dict]:
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")
        return None
