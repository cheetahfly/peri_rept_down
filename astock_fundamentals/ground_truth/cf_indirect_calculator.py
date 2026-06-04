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

Operations supported:
  - as_is:        use Sina column as-is
  - negate:       multiply by -1
  - sum:          sum of multiple columns
  - delta_pos:    sina_end - sina_begin (for CF items that increase)
  - delta_neg:    sina_begin - sina_end (for CF items that decrease)
  - sum_pos:      sum of (end - begin) for each source
  - sum_neg:      -(sum of (end - begin)) for each source
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

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
    operation: str  # see module docstring
    note: str = ""

    def compute(
        self,
        sina_is_row: Dict[str, float],
        sina_bs_end: Optional[Dict[str, float]] = None,
        sina_bs_begin: Optional[Dict[str, float]] = None,
    ) -> Optional[float]:
        """Apply the formula. Returns None if data missing.

        Args:
            sina_is_row: Sina IS dict (current year income statement)
            sina_bs_end: Sina BS dict (current year-end)
            sina_bs_begin: Sina BS dict (prior year-end)

        For IS-only ops (as_is/negate/sum), only sina_is_row is used.
        For BS-delta ops (delta_pos/delta_neg/sum_pos/sum_neg), both BS dicts required.
        """
        if self.operation == "as_is":
            v = sina_is_row.get(self.sina_sources[0])
            return float(v) if v is not None else None

        if self.operation == "negate":
            v = sina_is_row.get(self.sina_sources[0])
            return -float(v) if v is not None else None

        if self.operation == "sum":
            vals = [sina_is_row.get(s) for s in self.sina_sources]
            vals = [float(v) for v in vals if v is not None]
            return sum(vals) if vals else None

        # BS-delta operations require both periods
        if sina_bs_end is None or sina_bs_begin is None:
            return None

        if self.operation == "delta_pos":
            end = sina_bs_end.get(self.sina_sources[0])
            begin = sina_bs_begin.get(self.sina_sources[0])
            if end is None or begin is None:
                return None
            return float(end) - float(begin)

        if self.operation == "delta_neg":
            end = sina_bs_end.get(self.sina_sources[0])
            begin = sina_bs_begin.get(self.sina_sources[0])
            if end is None or begin is None:
                return None
            return float(begin) - float(end)

        if self.operation == "sum_pos":
            deltas = []
            for s in self.sina_sources:
                end = sina_bs_end.get(s)
                begin = sina_bs_begin.get(s)
                if end is not None and begin is not None:
                    deltas.append(float(end) - float(begin))
            return sum(deltas) if deltas else None

        if self.operation == "sum_neg":
            deltas = []
            for s in self.sina_sources:
                end = sina_bs_end.get(s)
                begin = sina_bs_begin.get(s)
                if end is not None and begin is not None:
                    deltas.append(float(end) - float(begin))
            return -sum(deltas) if deltas else None

        return None


def load_indirect_formulas() -> Dict[str, IndirectFormula]:
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


def compute_indirect_cf_for_period(
    cf_gt_items: Dict[str, float],
    sina_is_row: Dict[str, float],
    sina_bs_end: Optional[Dict[str, float]] = None,
    sina_bs_begin: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """Compute indirect-method CF items from Sina IS row + optional BS deltas.

    Args:
        cf_gt_items: RDS CF items (some indirect ones we want to match)
        sina_is_row: Sina IS row dict (one year's income statement)
        sina_bs_end: Sina BS end-of-period dict (current year)
        sina_bs_begin: Sina BS dict (prior year-end, for delta ops)

    Returns: {rds_cf_name: computed_value} for items that can be computed
    """
    formulas = load_indirect_formulas()
    out: Dict[str, float] = {}
    for rds_name in cf_gt_items:
        if rds_name in formulas:
            v = formulas[rds_name].compute(
                sina_is_row=sina_is_row,
                sina_bs_end=sina_bs_end,
                sina_bs_begin=sina_bs_begin,
            )
            if v is not None and not (v != v):  # skip NaN
                out[rds_name] = float(v)
    return out
