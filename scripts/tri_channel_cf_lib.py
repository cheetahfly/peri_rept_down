# -*- coding: utf-8 -*-
"""
Tri-channel CF 对比工具库：tushare vs RDS 现金流/三表对比。

复用 scripts/dual_channel_cf_lib.py 的 normalize/extract/best_match 逻辑，
新增 tushare 提取与三渠道匹配。
"""
from typing import Dict, List

import pandas as pd

from astock_fundamentals.sources.api import TushareProvider


def extract_tushare_year_values(provider: TushareProvider, stock_code: str, year: int) -> Dict[str, float]:
    """从 TushareProvider 拉取三表数据，返回带表名前缀的 dict。

    格式：{"[balance_sheet] total_assets": 100.0, ...}
    """
    out: Dict[str, float] = {}
    fetches = [
        ("balance_sheet", provider.get_balance_sheet),
        ("income_statement", provider.get_income_statement),
        ("cash_flow", provider.get_cash_flow),
    ]
    for stmt_type, get_fn in fetches:
        try:
            data = get_fn(stock_code, year)
        except Exception:
            continue
        if not data:
            continue
        for k, v in data.items():
            if isinstance(v, (int, float)):
                out[f"[{stmt_type}] {k}"] = float(v)
    return out


def tri_match(tushare_values: Dict[str, float], rds_standard: Dict[str, float]) -> List[Dict]:
    """对每个 RDS 项在 tushare 中找最佳匹配，返回分类清单。

    返回 list of:
      {rds_name, rds_value, tushare_label, tushare_value, abs_diff, rel_err_pct, class, color}
    """
    from dual_channel_cf_lib import best_match, classify_diff

    rows = []
    for rds_name, rds_v in rds_standard.items():
        if rds_v is None:
            continue
        ts_label, ts_v, diff, rel = best_match(rds_v, tushare_values)
        cls, color = classify_diff(diff, rel)
        rows.append({
            "rds_name": rds_name,
            "rds_value": rds_v,
            "tushare_label": ts_label,
            "tushare_value": ts_v,
            "abs_diff": diff,
            "rel_err_pct": rel,
            "class": cls,
            "color": color,
        })
    return rows
