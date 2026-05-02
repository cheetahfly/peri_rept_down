# -*- coding: utf-8 -*-
"""
现金流量表提取器
"""

import re
from typing import Dict, Tuple, List

from extraction.extractors.base import BaseExtractor
from extraction.config import SECTION_KEYWORDS


class CashFlowExtractor(BaseExtractor):
    """现金流量表提取器"""

    STATEMENT_TYPE = "cash_flow"
    SECTION_KEYWORDS = SECTION_KEYWORDS.get(
        "cash_flow",
        ["现金流量表", "合并现金流量表", "银行现金流量表", "合并及银行现金流量表"],
    )

    KEY_ITEMS = [
        # 经营活动产生的现金流量净额 - 标准及变体
        "经营活动产生的现金流量净额",
        "经营活动使用的现金流量净额",
        "经营活动(产生)/使用的现金流量净额",
        "经营活动产生的现金流量净额(使用)",
        "经营活(动)现金净流量",
        "经营活动现金净流量",
        "经营活动现金流量净额",
        "经营活动产生",  # 简化格式 (600000_2025)
        # 投资活动产生的现金流量净额 - 标准及变体
        "投资活动产生的现金流量净额",
        "投资活动使用的现金流量净额",
        "投资活动(产生)/使用的现金流量净额",
        "投资活动产生的现金流量净额(使用)",
        "投资活(动)现金净流量",
        "投资活动现金净流量",
        "投资活动现金流量净额",
        "投资活动产生的净现金流",  # 简化格式 (600000_2025)
        # 筹资活动产生的现金流量净额 - 标准及变体
        "筹资活动产生的现金流量净额",
        "筹资活动使用的现金流量净额",
        "筹资活动(产生)/使用的现金流量净额",
        "筹资活动产生的现金流量净额(使用)",
        "筹资活(动)现金净流量",
        "筹资活动现金净流量",
        "筹资活动现金流量净额",
        "筹资活动",  # 简化格式 (600000_2025)
        # 现金净增加/减少
        "现金及现金等价物净增加",
        "现金及现金等价物净减少",
        "现金及现金等价物净(增加)/减少",
        "现金及现金等价物净(减少)/增加",
        "现金净增加",
        "现金净减少",
        "现金及现金等价物净增加额",
        "现金及现金等价物净减少额",
        # 期末现金
        "期末现金及现金等价物余额",
        "年末现金及现金等价物余额",
        "期末现金",
        "年末现金",
        "现金的年末余额",
        "现金余额",
    ]

    STATEMENT_ITEMS = [
        "经营活动",
        "投资活动",
        "筹资活动",
        "现金",
        "存款",
        "贷款",
        "借款",
        "收到的现金",
        "支付的现金",
        "净增加",
        "净额",
    ]

    KEY_ITEM_PATTERNS = {
        "operating": [
            r"经营活动.*净额",
            r"经营活动(产生)/使用.*净额",
            r"经营.*现金流净额",
            r"经营活动现金流量净额",
            r"经营活动净现金流",
        ],
        "investing": [
            r"投资活动.*净额",
            r"投资活动(产生)/使用.*净额",
            r"投资.*现金流净额",
            r"投资活动现金流量净额",
            r"投资活动净现金流",
        ],
        "financing": [
            r"筹资活动.*净额",
            r"筹资活动(产生)/使用.*净额",
            r"筹资.*现金流净额",
            r"筹资活动现金流量净额",
            r"筹资活动净现金流",
            r"筹资活动产生",  # 截断情况
        ],
        "cash_end": [
            r"期末现金",
            r"现金余额",
            r"现金及现金等价物.*余额",
            r"现金的年末余额",
        ],
        "net_increase": [
            r"现金.*净[增加减少]",
            r"现金净[增加减少]",
            r"^[五六]、.*净[增加减少]",
            r"^[五六]、.*现金.*[增加减少]",
            r"现金及现金等价物净(增加|减少)",
            r"现金及现金等价物净(增加)/减少",
            r"现金及现金等价物净(减少)/增加",
        ],
    }

    def validate(self, data: Dict) -> Tuple[bool, str]:
        """
        验证现金流量表数据

        Args:
            data: 提取的数据

        Returns:
            (是否有效, 错误信息)
        """
        if not data.get("found"):
            return False, data.get("error", "未找到现金流量表")

        items = data.get("data", {})

        if not items:
            return False, "未提取到任何数据"

        if len(items) < 10:
            return False, f"数据过少，仅{len(items)}条"

        matched = self._count_key_items(items)
        if matched < 2:
            return False, f"关键科目过少，仅{matched}个"

        return True, ""

    def _count_key_items(self, items: Dict) -> int:
        """统计匹配的关键科目数量"""
        count = 0
        for key in items.keys():
            for pattern_list in self.KEY_ITEM_PATTERNS.values():
                for pattern in pattern_list:
                    if re.search(pattern, key):
                        count += 1
                        break
        return count

    def extract(self, pdf_path: str = None, discovered_pages: List[int] = None) -> Dict:
        """提取现金流量表"""
        return super().extract(pdf_path, discovered_pages)
