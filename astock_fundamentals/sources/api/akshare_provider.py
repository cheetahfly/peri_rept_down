# -*- coding: utf-8 -*-
"""
AKShare数据源 - 通过akshare获取新浪财经A股财务数据

安装: pip install akshare

AKShare 提供免费的中国金融市场数据API。
新浪财经数据源: https://vip.stock.finance.sina.com.cn/
"""
import warnings
from typing import Dict, Optional

import pandas as pd

from astock_fundamentals.sources.api import BaseApiProvider


# 新浪API的报表类型符号
SINA_SYMBOLS = {
    "balance_sheet": "资产负债表",
    "income_statement": "利润表",
    "cash_flow": "现金流量表",
}


class AKShareProvider(BaseApiProvider):
    """AKShare 新浪财经财务数据获取器"""
    name = "akshare_sina"

    def _fetch_sina(self, stock_code: str, symbol: str) -> Optional[pd.DataFrame]:
        """从新浪财经获取指定报表数据"""
        import akshare as ak
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = ak.stock_financial_report_sina(stock=stock_code, symbol=symbol)
            return df
        except Exception as e:
            import logging
            logging.warning(f"AKShare {symbol} fetch error for {stock_code}: {e}")
            return None

    def _extract_period(self, df: pd.DataFrame, year: int,
                        report_type: str) -> Optional[Dict[str, float]]:
        """
        从DataFrame中提取指定年份指定报告期的数据。

        AKShare新浪格式: row=报告期, col=科目名, values=数值
        如: 报告期=20201231, 货币资金=36,091,090,060.90
        """
        # 第一列是报告期（日期）
        period_series = df.iloc[:, 0].astype(str)

        # 确定要匹配的报告期
        target = {"annual": f"{year}1231", "half": f"{year}0630",
                  "q1": f"{year}0331", "q3": f"{year}0930"}.get(report_type, f"{year}1231")

        # 找目标行的索引
        mask = period_series == target
        if not mask.any():
            # 回退：找该年份最晚一期
            year_mask = period_series.str.startswith(str(year))
            if not year_mask.any():
                return None
            available = period_series[year_mask].tolist()
            target = sorted(available)[-1]
            mask = period_series == target

        row_idx = mask.idxmax() if mask.any() else -1
        if row_idx < 0:
            return None

        row = df.iloc[row_idx]
        result = {}
        for j in range(1, len(df.columns)):  # 跳过第一列（报告期）
            val = row.iloc[j]
            if pd.notna(val):
                item_name = str(df.columns[j])
                try:
                    result[item_name] = float(val)
                except (ValueError, TypeError):
                    continue
        return result

    def _get_data_sina(self, stock_code: str, year: int,
                       statement_type: str,
                       report_type: str = "annual") -> Optional[Dict[str, float]]:
        """获取单一报表数据"""
        symbol = SINA_SYMBOLS.get(statement_type)
        if not symbol:
            return None
        df = self._fetch_sina(stock_code, symbol)
        if df is None or df.empty:
            return None
        return self._extract_period(df, year, report_type)

    def get_balance_sheet(self, stock_code: str, year: int,
                          report_type: str = "annual") -> Optional[Dict]:
        return self._get_data_sina(stock_code, year, "balance_sheet", report_type)

    def get_income_statement(self, stock_code: str, year: int,
                             report_type: str = "annual") -> Optional[Dict]:
        return self._get_data_sina(stock_code, year, "income_statement", report_type)

    def get_cash_flow(self, stock_code: str, year: int,
                      report_type: str = "annual") -> Optional[Dict]:
        return self._get_data_sina(stock_code, year, "cash_flow", report_type)
