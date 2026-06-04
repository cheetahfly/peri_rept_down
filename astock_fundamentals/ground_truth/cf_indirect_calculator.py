# -*- coding: utf-8 -*-
"""
Compute indirect-method cash-flow items from Sina BS+IS data.

Indirect-method CF adjustments are formulaic relationships on BS/IS items:

  - 资产减值准备 = IS_资产减值损失 (often)
  - 固定资产折旧 = BS_累计折旧 (end) - BS_累计折旧 (begin) ... etc
  - 经营性应收项目的减少 = -(应收票据/账款增加 + 预付账款增加 + 其他应收款增加)
  - 经营性应付项目的增加 = 应付票据/账款增加 + 预收账款增加 + 其他应付款增加 + 应付职工薪酬增加
  - 存货的减少 = -(存货end - 存货begin)
  - 递延所得税资产减少 = -(递延所得税资产end - 递延所得税资产begin)
  - 递延所得税负债增加 = 递延所得税负债end - 递延所得税负债begin
  - 公允价值变动损失 = -IS_公允价值变动收益/(损失)
  - 投资损失 = -IS_投资收益
  - 处置固定资产...的损失 = IS_非流动资产处置损失
  - 固定资产报废损失 = IS_营业外支出 (估计)
  - 长期待摊费用摊销 = BS_长期待摊费用 (估计)
  - 无形资产摊销 = BS_累计摊销 (估计)
  - 现金及现金等价物净增加额 = BS_货币资金 (end) - BS_货币资金 (begin) (近似)

This module produces a mapping {RDS_CF_item: sina_name or formula} for use
in baseline_2019_2022 and the cleaning pipeline.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yaml

INDIRECT_CF_FORMULAS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "rules", "indirect_cf_formulas.yaml"
)


@dataclass
class IndirectFormula:
    """A formula for computing an indirect-method CF item from Sina BS/IS."""
    rds_cf_name: str
    sina_sources: List[str]  # Sina column names to read
    operation: str  # 'as_is', 'negate', 'sum', 'delta'
    note: str = ""

    def compute(self, sina_data: Dict[str, float]) -> Optional[float]:
        """Apply the formula to Sina data dict. Returns None if data missing."""
        if self.operation == "as_is":
            return sina_data.get(self.sina_sources[0])
        if self.operation == "negate":
            v = sina_data.get(self.sina_sources[0])
            return -v if v is not None else None
        if self.operation == "sum":
            vals = [sina_data.get(s) for s in self.sina_sources]
            vals = [v for v in vals if v is not None]
            return sum(vals) if vals else None
        return None


def load_indirect_formulas() -> Dict[str, IndirectFormula]:
    """Load the indirect CF formula registry from rules/indirect_cf_formulas.yaml."""
    if not os.path.exists(INDIRECT_CF_FORMULAS_PATH):
        return {}
    try:
        with open(INDIRECT_CF_FORMULAS_PATH, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}

    formulas: Dict[str, IndirectFormula] = {}
    for rds_name, spec in (doc.get("formulas") or {}).items():
        formulas[rds_name] = IndirectFormula(
            rds_cf_name=rds_name,
            sina_sources=spec.get("sources", []),
            operation=spec.get("op", "as_is"),
            note=spec.get("note", ""),
        )
    return formulas


# Default formulas (used if YAML not present)
DEFAULT_INDIRECT_FORMULAS: Dict[str, IndirectFormula] = {
    "加：资产减值准备": IndirectFormula(
        rds_cf_name="加：资产减值准备",
        sina_sources=["资产减值损失"],
        operation="as_is",
        note="IS_资产减值损失 (negate since CF subtracts)",
    ),
    "固定资产折旧、油气资产折耗、生产性生物资产折旧": IndirectFormula(
        rds_cf_name="固定资产折旧、油气资产折耗、生产性生物资产折旧",
        sina_sources=["折旧费"],
        operation="as_is",
        note="IS_折旧费 from income_statement",
    ),
    "无形资产摊销": IndirectFormula(
        rds_cf_name="无形资产摊销",
        sina_sources=["摊销"],
        operation="as_is",
        note="If Sina IS has 摊销 column",
    ),
    "投资损失": IndirectFormula(
        rds_cf_name="投资损失",
        sina_sources=["投资收益"],
        operation="negate",
        note="IS_投资收益 (negate since CF adds back loss)",
    ),
    "公允价值变动损失": IndirectFormula(
        rds_cf_name="公允价值变动损失",
        sina_sources=["公允价值变动收益/(损失)"],
        operation="negate",
        note="IS_公允价值变动 (negate since CF adds back loss)",
    ),
}


def compute_indirect_cf_for_period(
    cf_gt_items: Dict[str, float],
    sina_is_row: Dict[str, float],
) -> Dict[str, float]:
    """Compute indirect-method CF items from Sina IS row.

    Args:
        cf_gt_items: RDS CF items (some indirect ones we want to match)
        sina_is_row: Sina IS row dict (one year's income statement)

    Returns: {rds_cf_name: computed_value} for items that can be computed
    """
    formulas = load_indirect_formulas() or DEFAULT_INDIRECT_FORMULAS
    out: Dict[str, float] = {}
    for rds_name in cf_gt_items:
        if rds_name in formulas:
            v = formulas[rds_name].compute(sina_is_row)
            if v is not None:
                out[rds_name] = float(v)
    return out
