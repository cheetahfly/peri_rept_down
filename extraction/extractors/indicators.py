# -*- coding: utf-8 -*-
"""
财务指标提取器
"""

import re
from typing import Dict, Tuple, List, Optional

from extraction.extractors.base import BaseExtractor


class FinancialIndicatorsExtractor(BaseExtractor):
    """财务指标提取器"""

    STATEMENT_TYPE = "indicators"
    SECTION_KEYWORDS = ["主要财务指标", "财务指标", "主要会计数据"]

    # 常见财务指标关键词
    INDICATOR_PATTERNS = {
        # 盈利能力
        "净资产收益率": ["净资产收益率", "ROE", "股东权益收益率"],
        "总资产收益率": ["总资产收益率", "ROA", "资产收益率"],
        "毛利率": ["毛利率", "毛利润率"],
        "净利率": ["净利率", "净利润率", "销售净利率"],
        "营业利润率": ["营业利润率"],

        # 偿债能力
        "资产负债率": ["资产负债率"],
        "流动比率": ["流动比率"],
        "速动比率": ["速动比率"],
        "现金比率": ["现金比率"],

        # 运营能力
        "应收账款周转率": ["应收账款周转率"],
        "存货周转率": ["存货周转率"],
        "总资产周转率": ["总资产周转率"],
        "固定资产周转率": ["固定资产周转率"],

        # 成长能力
        "营业收入增长率": ["营业收入增长率", "营收增长率"],
        "净利润增长率": ["净利润增长率"],
        "总资产增长率": ["总资产增长率"],
        "股东权益增长率": ["股东权益增长率"],

        # 每股数据
        "每股收益": ["每股收益", "EPS", "基本每股收益", "稀释每股收益"],
        "每股净资产": ["每股净资产", "BPS"],
        "每股经营现金流": ["每股经营现金流量", "每股经营现金流"],
    }

    def validate(self, data: Dict) -> Tuple[bool, str]:
        """验证财务指标数据"""
        if not data.get("found"):
            return False, data.get("error", "未找到财务指标")

        items = data.get("data", {})
        if not items:
            return False, "未提取到任何指标数据"

        return True, ""

    def extract(self, pdf_path: str = None) -> Dict:
        """提取财务指标"""
        return super().extract(pdf_path)

    def _merge_tables(self, tables: List[Tuple[int, object]]) -> Dict[str, float]:
        """重写表格合并逻辑，直接提取指标"""
        all_items = {}

        for page_num, table in tables:
            try:
                items = self._extract_indicators_from_table(table)
                all_items.update(items)
            except Exception:
                continue

        return all_items

    def _extract_indicators_from_table(self, table) -> Dict[str, float]:
        """从表格提取财务指标"""
        items = {}

        for idx, row in table.iterrows():
            # 获取第一列作为指标名称
            indicator_name = str(row.iloc[0]) if len(row) > 0 else ""
            indicator_name = self.table_parser.clean_text(indicator_name)

            if not indicator_name or indicator_name in ["项目", "指标名称", ""]:
                continue

            # 匹配指标名称
            matched_key = self._match_indicator(indicator_name)
            if not matched_key:
                continue

            # 提取数值（通常在第二列或第三列）
            value = None
            for col_idx in range(1, min(len(row), 5)):
                cell_value = row.iloc[col_idx]
                if self.table_parser.pd.notna(cell_value):
                    parsed = self.table_parser.parse_number(cell_value)
                    if parsed is not None:
                        value = parsed
                        break

            if value is not None:
                items[matched_key] = value

        return items

    def _match_indicator(self, name: str) -> Optional[str]:
        """匹配指标名称"""
        name = name.lower()

        for indicator_key, keywords in self.INDICATOR_PATTERNS.items():
            for kw in keywords:
                if kw.lower() in name:
                    return indicator_key

        return None


class RatioCalculator:
    """财务比率计算器"""

    @staticmethod
    def calculate_ratios(balance_sheet: Dict, income_statement: Dict, cash_flow: Dict) -> Dict:
        """
        计算财务比率

        Args:
            balance_sheet: 资产负债表数据
            income_statement: 利润表数据
            cash_flow: 现金流量表数据

        Returns:
            财务比率字典
        """
        ratios = {}

        # 盈利能力
        ratios["盈利能力"] = RatioCalculator._calc_profitability_ratios(income_statement)

        # 偿债能力
        ratios["偿债能力"] = RatioCalculator._calc_solvency_ratios(balance_sheet)

        # 运营能力
        ratios["运营能力"] = RatioCalculator._calc_activity_ratios(balance_sheet, income_statement)

        return ratios

    @staticmethod
    def _calc_profitability_ratios(income_data: Dict) -> Dict:
        """计算盈利能力指标"""
        ratios = {}

        # 从income_data中提取
        revenue = income_data.get("营业收入", income_data.get("营业总收入", 0))
        net_profit = income_data.get("净利润", 0)
        total_assets = income_data.get("资产总计", 0)
        equity = income_data.get("所有者权益合计", income_data.get("股东权益合计", 0))

        if revenue > 0:
            ratios["净利率"] = round(net_profit / revenue * 100, 2)

        if equity > 0:
            ratios["净资产收益率(ROE)"] = round(net_profit / equity * 100, 2)

        if total_assets > 0:
            ratios["总资产收益率(ROA)"] = round(net_profit / total_assets * 100, 2)

        return ratios

    @staticmethod
    def _calc_solvency_ratios(balance_sheet: Dict) -> Dict:
        """计算偿债能力指标"""
        ratios = {}

        total_assets = balance_sheet.get("资产总计", 0)
        total_liabilities = balance_sheet.get("负债合计", balance_sheet.get("负债总计", 0))
        current_assets = balance_sheet.get("流动资产合计", 0)
        current_liabilities = balance_sheet.get("流动负债合计", 0)
        cash = balance_sheet.get("货币资金", 0)

        if total_assets > 0:
            ratios["资产负债率"] = round(total_liabilities / total_assets * 100, 2)

        if current_liabilities > 0:
            ratios["流动比率"] = round(current_assets / current_liabilities, 2)

            quick_assets = current_assets - balance_sheet.get("存货", 0)
            ratios["速动比率"] = round(quick_assets / current_liabilities, 2)

            ratios["现金比率"] = round(cash / current_liabilities, 2)

        return ratios

    @staticmethod
    def _calc_activity_ratios(balance_sheet: Dict, income_data: Dict) -> Dict:
        """计算运营能力指标"""
        ratios = {}

        revenue = income_data.get("营业收入", 0)
        total_assets = balance_sheet.get("资产总计", 0)
        accounts_receivable = balance_sheet.get("应收账款", 0)
        inventory = balance_sheet.get("存货", 0)

        if total_assets > 0 and revenue > 0:
            ratios["总资产周转率"] = round(revenue / total_assets, 2)

        if accounts_receivable > 0:
            ratios["应收账款周转率"] = round(revenue / accounts_receivable, 2)

        if inventory > 0:
            cost = income_data.get("营业成本", 0)
            if cost > 0:
                ratios["存货周转率"] = round(cost / inventory, 2)

        return ratios
