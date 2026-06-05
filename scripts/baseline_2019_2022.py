#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Baseline: compare Sina 2019-2022 annual vs RDS ground truth.

For cash_flow, filters RDS gt_data to only direct-method items
(those that exist in Sina CF or IS), excluding indirect-method
adjustments that Sina does not provide.
"""

import json
import os
import sys
from typing import Dict, List, Set

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.ground_truth.sina_loader import SinaLoader
from astock_fundamentals.sources.guosen import GuosenLoader, GuosenAuthError
from astock_fundamentals.ground_truth.comparator import compare_stock
from astock_fundamentals.ground_truth.cf_indirect_calculator import (
    compute_indirect_cf_for_period,
)
from astock_fundamentals.core.extraction_config import get_aliases

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE, "data", "akshare_bulk")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
CF_DIRECT_PATH = os.path.join(BASE, "rules", "cf_direct_items.yaml")
OUTPUT = os.path.join(BASE, "data", "ground_truth_reports", "baseline_2019_2022.json")

DEFAULT_YEARS = [2019, 2020, 2021, 2022]
DEFAULT_SAMPLE_STOCKS = ["000001", "600000", "600036", "600519", "000002", "000858"]
EXPANDED_STOCK_LIST = os.path.join(BASE, "data", "ground_truth_reports", "expanded_stock_list.txt")


def _load_sample_stocks() -> List[str]:
    """Load expanded stock list if available, else default."""
    if os.path.exists(EXPANDED_STOCK_LIST):
        with open(EXPANDED_STOCK_LIST, "r", encoding="utf-8") as f:
            stocks = [line.strip() for line in f if line.strip()]
        if stocks:
            return stocks
    return DEFAULT_SAMPLE_STOCKS


SAMPLE_STOCKS = _load_sample_stocks()
STATEMENT_TYPES = ["balance_sheet", "income_statement", "cash_flow"]
META_COLS = {"报告日", "数据源", "是否审计", "公告日期", "币种", "类型", "更新日期"}


def _load_cf_direct_sets() -> (Set[str], Set[str]):
    """Return (direct_items, is_cross_items) for CF filtering."""
    direct: Set[str] = set()
    cross: Set[str] = set()
    try:
        with open(CF_DIRECT_PATH, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        items = doc.get("cf_direct_items", {}).get("cash_flow", []) or []
        direct = set(items)
        cross_items = doc.get("cf_direct_items", {}).get("cf_is_cross_items", []) or []
        cross = set(cross_items)
    except Exception:
        pass
    return direct, cross


def _load_decode_map(path: str) -> Dict[str, Dict[str, str]]:
    """Load the by-type decode map; tolerate encoding issues."""
    for enc in ("utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except UnicodeDecodeError:
            continue
    with open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8", errors="replace"))


def _sina_row_to_ext_dict(row) -> Dict[str, float]:
    """Convert a Sina DataFrame row to a numeric dict for compare_stock."""
    out = {}
    for k, v in row.items():
        if k in META_COLS:
            continue
        if v is None:
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def main():
    import argparse
    p = argparse.ArgumentParser(description="Baseline Sina vs RDS comparison")
    p.add_argument("--years", nargs="+", default=[2019, 2020, 2021, 2022],
                   help="Years to process")
    p.add_argument("--cache-dir", default=CACHE_DIR)
    p.add_argument("--source", choices=["sina", "guosen"], default="sina",
                   help="Data source")
    args = p.parse_args()
    years = sorted({int(y) for y in args.years})

    if args.source == "guosen":
        try:
            sina = GuosenLoader()
        except GuosenAuthError as e:
            print(f"ERROR: {e}")
            return 1
    else:
        sina = SinaLoader(args.cache_dir)
    rds = RdsLoader(RDS_DIR, decode_map_path=DECODE_PATH)
    decode_maps = _load_decode_map(DECODE_PATH)
    cf_direct, cf_is_cross = _load_cf_direct_sets()

    # Pre-load Sina IS and BS data for CF cross-item injection + indirect calc
    sina_is_cache: Dict[str, Dict[int, Dict[str, float]]] = {}
    sina_bs_cache: Dict[str, Dict[int, Dict[str, float]]] = {}
    for code in SAMPLE_STOCKS:
        # IS
        try:
            is_df = sina.get_annual(code, years, "income_statement")
        except FileNotFoundError:
            is_df = None
        sina_is_cache[code] = {}
        if is_df is not None:
            for _, row in is_df.iterrows():
                period = str(row.get("报告日", ""))
                if not period.endswith("1231"):
                    continue
                year = int(period[:4])
                ext_is = {}
                for k, v in row.items():
                    if k in META_COLS or v is None:
                        continue
                    try:
                        ext_is[k] = float(v)
                    except (TypeError, ValueError):
                        continue
                sina_is_cache[code][year] = ext_is

        # BS — load also prior year (year-1) for delta computation
        try:
            bs_df = sina.get_annual(code, [y - 1 for y in years] + years, "balance_sheet")
        except FileNotFoundError:
            bs_df = None
        sina_bs_cache[code] = {}
        if bs_df is not None:
            for _, row in bs_df.iterrows():
                period = str(row.get("报告日", ""))
                if not period.endswith("1231"):
                    continue
                year = int(period[:4])
                ext_bs = {}
                for k, v in row.items():
                    if k in META_COLS or v is None:
                        continue
                    try:
                        ext_bs[k] = float(v)
                    except (TypeError, ValueError):
                        continue
                sina_bs_cache[code][year] = ext_bs

    results: List[dict] = []
    for code in SAMPLE_STOCKS:
        for st in STATEMENT_TYPES:
            try:
                sina_df = sina.get_annual(code, years, st)
            except FileNotFoundError:
                continue
            if sina_df.empty:
                continue
            alias_map = get_aliases(st, "annual") or {}
            decode_for_st = decode_maps.get(st, {})
            for _, row in sina_df.iterrows():
                period = str(row.get("报告日", ""))
                if not period.endswith("1231"):
                    continue
                year = int(period[:4])
                gt_data = rds.load_stock_data(code, year, st)
                if not gt_data:
                    continue
                ext_data = _sina_row_to_ext_dict(row)

                # CF: filter to direct-method items only (indirect items kept out of
                # denominator since Sina BS-delta error vs RDS is too high to
                # count as a reliable match). Indirect items CAN be computed and
                # injected into ext_data for opportunistic matching, but won't
                # count as "missing" if not matched.
                if st == "cash_flow" and cf_direct:
                    is_cache = sina_is_cache.get(code, {}).get(year, {})
                    bs_end = sina_bs_cache.get(code, {}).get(year, {})
                    bs_begin = sina_bs_cache.get(code, {}).get(year - 1, {})
                    # Restrict denominator to direct + IS-cross items only
                    gt_data = {k: v for k, v in gt_data.items() if k in cf_direct or k in cf_is_cross}
                    # Inject IS-cross items (净利润, 财务费用, etc.)
                    for cross_item in cf_is_cross:
                        if cross_item not in ext_data and cross_item in is_cache:
                            ext_data[cross_item] = is_cache[cross_item]
                    # Opportunistic: compute indirect items and inject, but don't
                    # expand the denominator. If they match, bonus; if not, no penalty.
                    indirect_keys = {k: v for k, v in rds.load_stock_data(code, year, "cash_flow").items()
                                     if k not in cf_direct and k not in cf_is_cross}
                    indirect_computed = compute_indirect_cf_for_period(
                        indirect_keys, is_cache, bs_end, bs_begin,
                    )
                    for ir_name, ir_val in indirect_computed.items():
                        ext_data[ir_name] = ir_val

                if not gt_data or not ext_data:
                    continue
                comp = compare_stock(
                    gt_data=gt_data,
                    ext_data=ext_data,
                    alias_map=alias_map,
                    stock_code=code,
                    year=year,
                    statement_type=st,
                    decode_map=decode_for_st,
                )
                s = comp.summary()
                results.append(s)

    by_stmt: Dict[str, dict] = {}
    for r in results:
        k = r["statement_type"]
        by_stmt.setdefault(k, {"comparisons": 0, "gt_items": 0, "matched": 0,
                                "value_acc_sum": 0.0, "value_acc_n": 0})
        by_stmt[k]["comparisons"] += 1
        by_stmt[k]["gt_items"] += r["gt_items"]
        by_stmt[k]["matched"] += r["matched"]
        by_stmt[k]["value_acc_sum"] += r["value_accuracy"]
        by_stmt[k]["value_acc_n"] += 1

    summary = {
        "scope": f"{len(SAMPLE_STOCKS)} stocks x {years} x {len(STATEMENT_TYPES)}",
        "stocks_sampled": SAMPLE_STOCKS,
        "total_comparisons": len(results),
        "by_statement": {
            k: {
                "comparisons": v["comparisons"],
                "rds_items": v["gt_items"],
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