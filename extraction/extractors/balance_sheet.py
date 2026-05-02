# -*- coding: utf-8 -*-
"""
资产负债表提取器
"""

import re
from typing import Dict, Tuple, List, Optional

from extraction.extractors.base import BaseExtractor
from extraction.config import SECTION_KEYWORDS


class BalanceSheetExtractor(BaseExtractor):
    """资产负债表提取器"""

    STATEMENT_TYPE = "balance_sheet"
    SECTION_KEYWORDS = SECTION_KEYWORDS.get("balance_sheet", ["资产负债表"])

    KEY_ITEMS = [
        "资产总计",
        "资产合计",
        "资产总额",
        "负债合计",
        "负债总计",
        "负债总额",
        "所有者权益合计",
        "股东权益合计",
        "归属母公司股东权益合计",
        "归属母公司权益合计",
    ]

    STATEMENT_ITEMS = [
        "资产",
        "负债",
        "权益",
        "流动资产",
        "非流动资产",
        "货币资金",
        "应收",
        "存货",
        "固定资产",
        "无形资产",
        "短期借款",
        "长期借款",
        "应付",
        "所有者权益",
    ]

    KEY_ITEM_PATTERNS = {
        "assets_total": [r"资产总计", r"资产合计", r"资产总额", r"资产总计数"],
        "liabilities_total": [r"负债合计", r"负债总计", r"负债总额", r"负债总计数"],
        "equity_total": [
            r"所有者权益合计",
            r"股东权益合计",
            r"所有者权益总计",
            r"股东权益总计",
            r"权益合计",
        ],
        "current_assets": [r"流动资产合计", r"流动资产总额"],
        "non_current_assets": [r"非流动资产合计", r"非流动资产总额"],
        "current_liabilities": [r"流动负债合计", r"流动负债总额"],
        "non_current_liabilities": [r"非流动负债合计", r"非流动负债总额"],
    }

    def validate(self, data: Dict) -> Tuple[bool, str]:
        """
        验证资产负债表数据

        Args:
            data: 提取的数据

        Returns:
            (是否有效, 错误信息)
        """
        if not data.get("found"):
            return False, data.get("error", "未找到资产负债表")

        items = data.get("data", {})

        if not items:
            return False, "未提取到任何数据"

        if self._count_key_items(items) < 2:
            return False, f"关键科目过少，可能提取不完整"

        assets_total = self._find_total_by_pattern(items, "assets_total")
        liabilities_total = self._find_total_by_pattern(items, "liabilities_total")
        equity_total = self._find_total_by_pattern(items, "equity_total")

        if assets_total and liabilities_total and equity_total:
            total_check = liabilities_total + equity_total
            diff = abs(assets_total - total_check)
            tolerance = abs(assets_total * 0.01)
            if diff > tolerance:
                return (
                    False,
                    f"资产负债表不平衡: 资产={assets_total}, 负债+权益={total_check}, 差异={diff}",
                )

        return True, ""

    def _count_key_items(self, items: Dict) -> int:
        """统计关键科目数量"""
        count = 0
        for key in items.keys():
            for pattern_list in self.KEY_ITEM_PATTERNS.values():
                for pattern in pattern_list:
                    if re.search(pattern, key):
                        count += 1
                        break
        return count

    def _find_total_by_pattern(self, items: Dict, pattern_key: str) -> Optional[float]:
        """根据模式查找合计项"""
        patterns = self.KEY_ITEM_PATTERNS.get(pattern_key, [])
        for key in items.keys():
            for pattern in patterns:
                if re.search(pattern, key):
                    return items[key]
        return None

    def _find_total(self, items: Dict, keywords: List[str]) -> float:
        """查找合计项"""
        for key in items:
            for kw in keywords:
                if kw in key:
                    return items[key]
        return None

    def extract(self, pdf_path: str = None, discovered_pages: List[int] = None) -> Dict:
        """提取资产负债表"""
        return super().extract(pdf_path, discovered_pages)
