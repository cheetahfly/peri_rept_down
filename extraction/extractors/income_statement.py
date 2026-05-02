# -*- coding: utf-8 -*-
"""
利润表/损益表提取器
"""

import re
from typing import Dict, Tuple, List, Optional

from extraction.extractors.base import BaseExtractor
from extraction.config import SECTION_KEYWORDS


class IncomeStatementExtractor(BaseExtractor):
    """利润表/损益表提取器"""

    STATEMENT_TYPE = "income_statement"
    SECTION_KEYWORDS = SECTION_KEYWORDS.get("income_statement", ["利润表", "损益表", "合并利润表"])

    # 关键科目
    KEY_ITEMS = [
        "营业收入", "利润总额", "净利润", "所得税费用",
        "营业利润",
    ]

    # 用于过滤表格的关键词
    STATEMENT_ITEMS = [
        "营业收入", "营业成本", "营业利润", "利润总额", "净利润",
        "利息净收入", "手续费及佣金", "业务及管理费",
        "所得税", "公允价值变动", "投资收益",
    ]

    def validate(self, data: Dict) -> Tuple[bool, str]:
        """
        验证利润表数据

        Args:
            data: 提取的数据

        Returns:
            (是否有效, 错误信息)
        """
        if not data.get("found"):
            return False, data.get("error", "未找到利润表")

        items = data.get("data", {})

        if not items:
            return False, "未提取到任何数据"

        # 检查是否有净利润
        has_net_profit = any("净利润" in k for k in items.keys())
        if not has_net_profit:
            return False, "缺少净利润科目"

        # 检查是否有营业收入
        has_revenue = any("营业收入" in k or "营业总收入" in k for k in items.keys())
        if not has_revenue:
            return False, "缺少营业收入科目"

        return True, ""

    def extract(self, pdf_path: str = None, discovered_pages: List[int] = None) -> Dict:
        """提取利润表"""
        return super().extract(pdf_path, discovered_pages)
