# -*- coding: utf-8 -*-
"""
Label recovery for CID-font garbled PDFs.

Recovers financial item labels (e.g. 经营活动产生的现金流量净额)
from position-based keys (e.g. p161_r1_c1) using y-position matching
against reference PDFs or standard financial statement templates.
"""
from typing import Dict, List, Optional, Tuple

# =============================================================================
# Standard Financial Statement Templates (证监会格式)
# =============================================================================

BS_TEMPLATE = [
    "流动资产合计",          # 0
    "非流动资产合计",        # 1
    "资产总计",              # 2
    "流动负债合计",          # 3
    "非流动负债合计",        # 4
    "负债合计",              # 5
    "所有者权益合计",        # 6
    "负债和所有者权益总计",  # 7
]

IS_TEMPLATE = [
    "营业收入",              # 0
    "营业成本",              # 1
    "销售费用",              # 2
    "管理费用",              # 3
    "研发费用",              # 4
    "财务费用",              # 5
    "资产减值损失",          # 6
    "公允价值变动收益",      # 7
    "投资收益",              # 8
    "营业利润",              # 9
    "营业外收入",            # 10
    "营业外支出",            # 11
    "利润总额",              # 12
    "所得税费用",            # 13
    "净利润",                # 14
    "归属于母公司所有者的净利润",  # 15
]

CF_TEMPLATE = [
    "一、经营活动产生的现金流量净额",     # 0
    "其中：取得投资收益收到的现金",      # 1
    "处置固定资产、无形资产收回的现金净额", # 2
    "处置子公司收到的现金净额",          # 3
    "收到其他与经营活动有关的现金",     # 4
    "经营活动现金流出小计",             # 5
    "经营活动产生的现金流量净额",        # 6
    "二、投资活动产生的现金流量净额",     # 7
    "其中：收回投资收到的现金",          # 8
    "取得投资收益收到的现金",            # 9
    "处置固定资产、无形资产支付的现金",  # 10
    "购建固定资产、无形资产支付的现金",  # 11
    "投资支付的现金",                    # 12
    "投资活动现金流出小计",             # 13
    "投资活动产生的现金流量净额",        # 14
    "三、筹资活动产生的现金流量净额",     # 15
    "其中：吸收投资收到的现金",          # 16
    "取得借款收到的现金",                # 17
    "发行债券收到的现金",               # 18
    "筹资活动现金流入小计",             # 19
    "偿还债务支付的现金",               # 20
    "分配股利、利润或偿付利息支付的现金", # 21
    "筹资活动现金流出小计",             # 22
    "筹资活动产生的现金流量净额",        # 23
    "四、汇率变动对现金的影响",         # 24
    "五、现金及现金等价物净增加额",     # 25
    "加：期初现金及现金等价物余额",     # 26
    "六、期末现金及现金等价物余额",     # 27
]

TEMPLATE_MAP = {
    "balance_sheet": BS_TEMPLATE,
    "income_statement": IS_TEMPLATE,
    "cash_flow": CF_TEMPLATE,
}


def _load_template(statement_type: str) -> List[str]:
    """Return standard template item list for the statement type."""
    return TEMPLATE_MAP.get(statement_type, [])
