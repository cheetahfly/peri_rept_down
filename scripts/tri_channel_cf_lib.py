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
