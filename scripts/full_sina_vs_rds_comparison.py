#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Full comparison: Sina (via rules) vs RDS ground truth.

Uses all learned rules from rules/*.yaml, applies to Sina data,
then compares with RDS ground truth. Produces accuracy metrics.
"""

import json
import os
import sys
import time
from typing import Dict, List

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.ground_truth.sina_loader import SinaLoader
from astock_fundamentals.ground_truth.comparator import compare_stock
from astock_fundamentals.ground_truth.rule_cleaner import load_cleaning_rules
from astock_fundamentals.sources.rds.rds_loader import RdsLoader, FINANCIAL_CODES
from astock_fundamentals.core.extraction_config import get_aliases

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE, "data", "akshare_bulk")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
FIELD_ORDER_PATH = os.path.join(BASE, "rules", "field_order.yaml")

OUTPUT = os.path.join(BASE, "data", "ground_truth_reports", "full_sina_vs_rds_200stocks.json")

STATEMENT_TYPES = ["balance_sheet", "income_statement", "cash_flow"]

# Sample 200 stocks (first 200 from expanded list)
EXPANDED_STOCK_LIST = os.path.join(BASE, "data", "ground_truth_reports", "expanded_stock_list.txt")


def _load_sample_stocks(n: int = 200) -> List[str]:
    """Load first n stocks from expanded list."""
    if os.path.exists(EXPANDED_STOCK_LIST):
        with open(EXPANDED_STOCK_LIST, "r", encoding="utf-8") as f:
            stocks = [line.strip() for line in f if line.strip()][:n]
        return stocks
    # Fallback: first 200 codes from akshare_bulk
    stocks = []
    for f in sorted(os.listdir(CACHE_DIR)):
        if f.endswith("_balance_sheet.csv") and len(stocks) < n:
            stocks.append(f.split("_")[0])
    return stocks


def _load_decode_map(path: str) -> Dict[str, Dict[str, str]]:
    """Load by-type decode map."""
    for enc in ("utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except UnicodeDecodeError:
            continue
    with open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8", errors="replace"))


def _sina_row_to_dict(row) -> Dict[str, float]:
    """Convert Sina row to numeric dict."""
    META = {"报告日", "数据源", "是否审计", "公告日期", "币种", "类型", "更新日期"}
    out = {}
    for k, v in row.items():
        if k in META:
            continue
        if v is None:
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def main():
    SAMPLES = _load_sample_stocks(200)
    print(f"Sample: {len(SAMPLES)} stocks, first 3: {SAMPLES[:3]}", flush=True)

    # Years to compare: 2019-2022 (4 years)
    YEARS = [2019, 2020, 2021, 2022]
    print(f"Years: {YEARS}", flush=True)

    # Load Sina data
    sina = SinaLoader(CACHE_DIR)

    # Load RDS (optimized: use bulk index building)
    rds = RdsLoader(RDS_DIR, decode_map_path=DECODE_PATH)
    decode_maps = _load_decode_map(DECODE_PATH)
    rules = load_cleaning_rules()

    print("Building RDS indices...", flush=True)
    rds_indices = {}  # {statement_type: {(stock, year): {chinese_name: value}}}
    for st in STATEMENT_TYPES:
        start = time.time()
        rds_indices[st] = {}
        for is_fin in [True, False]:
            filename = {
                "balance_sheet": "b_f.rds" if is_fin else "b_o.rds",
                "income_statement": "pl_f.rds" if is_fin else "pl_o.rds",
                "cash_flow": "cf_f.rds" if is_fin else "cf_o.rds",
            }.get(st)
            if not filename:
                continue
            try:
                df = rds._load_rds(filename)
                if df is None or len(df) == 0:
                    continue
                decode_for_st = decode_maps.get(st, {})
                # Build index from df directly
                if "SECCODE" not in df.columns or "ENDDATE" not in df.columns:
                    continue
                df_year = df["ENDDATE"].astype(str).str[:4]
                decode_cols = [c for c in df.columns if c in decode_for_st]
                for stock_code, year_str, row in zip(df["SECCODE"], df_year, df[decode_cols].itertuples(index=False, name=None)):
                    try:
                        y = int(year_str)
                    except (ValueError, TypeError):
                        continue
                    key = (str(stock_code), y)
                    data = {}
                    has_value = False
                    for col, val in zip(decode_cols, row):
                        if val is not None and str(val) != "nan":
                            try:
                                data[decode_for_st[col]] = float(val)
                                has_value = True
                            except (ValueError, TypeError):
                                pass
                    if has_value and key not in rds_indices[st]:
                        rds_indices[st][key] = data
            except Exception as e:
                print(f"  WARN: failed to load {filename}: {e}", flush=True)
        print(f"  {st}: {len(rds_indices[st])} (stock, year) cells indexed", flush=True)

    # Compare Sina vs RDS for each (stock, year, statement)
    results = []
    total_cells = len(SAMPLES) * len(YEARS) * len(STATEMENT_TYPES)
    processed = 0
    for stock_code in SAMPLES:
        for year in YEARS:
            for st in STATEMENT_TYPES:
                processed += 1
                if processed % 100 == 0:
                    print(f"  {processed}/{total_cells} processed", flush=True)

                # Get RDS ground truth
                rds_data = rds_indices.get(st, {}).get((stock_code, year))
                if not rds_data:
                    continue

                # Get Sina raw data
                try:
                    sina_df = sina.get_annual(stock_code, [year], st)
                    if sina_df is None or sina_df.empty:
                        continue
                except Exception:
                    continue

                # Convert Sina rows to dict
                sina_dict = {}
                for _, row in sina_df.iterrows():
                    period = str(row.get("报告日", ""))
                    if not period.endswith("1231"):
                        continue
                    y = int(period[:4])
                    if y == year:
                        sina_dict = _sina_row_to_dict(row)
                        break

                if not sina_dict:
                    continue

                # Get aliases for this statement type
                alias_map = get_aliases(st, "annual") or {}
                decode_for_st = decode_maps.get(st, {})

                # Compare using comparator
                comp = compare_stock(
                    gt_data=rds_data,
                    ext_data=sina_dict,
                    alias_map=alias_map,
                    stock_code=stock_code,
                    year=year,
                    statement_type=st,
                    decode_map=decode_for_st,
                )
                s = comp.summary()
                results.append(s)

    # Aggregate
    by_stmt = {}
    for r in results:
        k = r["statement_type"]
        by_stmt.setdefault(k, {"comparisons": 0, "gt_items": 0, "matched": 0, "value_acc_sum": 0.0, "value_acc_n": 0})
        by_stmt[k]["comparisons"] += 1
        by_stmt[k]["gt_items"] += r["gt_items"]
        by_stmt[k]["matched"] += r["matched"]
        by_stmt[k]["value_acc_sum"] += r["value_accuracy"]
        by_stmt[k]["value_acc_n"] += 1

    summary = {
        "scope": f"{len(SAMPLES)} stocks x {len(YEARS)} years x {len(STATEMENT_TYPES)} statements",
        "source": "Sina via full_rules + RDS ground truth",
        "total_comparisons": len(results),
        "by_statement": {
            k: {
                "comparisons": v["comparisons"],
                "gt_items": v["gt_items"],
                "matched": v["matched"],
                "match_rate": round(v["matched"] / v["gt_items"], 4) if v["gt_items"] else 0,
                "avg_value_accuracy": round(v["value_acc_sum"] / v["value_acc_n"], 4) if v["value_acc_n"] else 0,
            } for k, v in by_stmt.items()
        },
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
