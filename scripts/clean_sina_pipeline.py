#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sina→RDS cleaning pipeline orchestrator.

Steps:
1. Slice Sina 2019-2022 annual rows
2. Match against RDS via existing comparator
3. Emit matching report (JSON)
4. Apply externalized cleaning rules (rename / unit / aggregate)
5. Write Tidy Data CSV aligned to field_order.yaml display_order
"""

import argparse
import json
import os
import sys
from typing import Dict, List

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.ground_truth.sina_loader import SinaLoader
from astock_fundamentals.ground_truth.rule_cleaner import (
    load_cleaning_rules, rename_columns, convert_values, apply_aggregations,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CACHE = os.path.join(BASE, "data", "akshare_bulk")
DEFAULT_OUTPUT = os.path.join(BASE, "data", "exports_v2")
DEFAULT_REPORT_DIR = os.path.join(BASE, "data", "ground_truth_reports")
FIELD_ORDER_PATH = os.path.join(BASE, "rules", "field_order.yaml")


def _parse_years(values: List[str]) -> List[int]:
    return [int(v) for v in values]


def _load_field_order() -> Dict[str, Dict[str, int]]:
    with open(FIELD_ORDER_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _tidy_rows(
    df: pd.DataFrame,
    statement_type: str,
    field_order: Dict[str, Dict[str, int]],
    stock_code: str,
) -> pd.DataFrame:
    """Pivot wide cleaned rows into Tidy (one row per field per period)."""
    order_map = field_order.get(statement_type, {})
    rows: List[dict] = []
    for _, row in df.iterrows():
        period = str(row.get("报告日", ""))
        for canonical, order in order_map.items():
            if canonical in df.columns:
                value = row[canonical]
                if pd.notna(value):
                    rows.append({
                        "stock_code": stock_code,
                        "year": int(period[:4]) if period else 0,
                        "period": "annual",
                        "statement_type": statement_type,
                        "field_name": canonical,
                        "value": float(value),
                        "display_order": order,
                    })
    return pd.DataFrame(rows)


def run_pipeline(
    stocks: List[str],
    years: List[int],
    cache_dir: str,
    output_dir: str,
    report_dir: str,
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)
    field_order = _load_field_order()
    rules = load_cleaning_rules()

    summary: Dict[str, dict] = {}
    tidy_frames: Dict[str, List[pd.DataFrame]] = {
        "balance_sheet": [],
        "income_statement": [],
        "cash_flow": [],
    }

    loader = SinaLoader(cache_dir)
    for code in stocks:
        for st in ["balance_sheet", "income_statement", "cash_flow"]:
            try:
                sina_df = loader.get_annual(code, years, st)
            except FileNotFoundError:
                continue
            if sina_df.empty:
                continue
            cleaned = rename_columns(sina_df, st, rules)
            cleaned = convert_values(cleaned, rules)
            cleaned = apply_aggregations(cleaned, st, rules)
            tidy_frames[st].append(_tidy_rows(cleaned, st, field_order, code))
            summary.setdefault(st, {"stocks": set(), "rows": 0})
            summary[st]["stocks"].add(code)
            summary[st]["rows"] += len(cleaned)

    for st, frames in tidy_frames.items():
        if not frames:
            continue
        out_df = pd.concat(frames, ignore_index=True)
        out_path = os.path.join(output_dir, f"sina_cleaned_{st}.csv")
        out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"  wrote {len(out_df)} rows to {out_path}")

    summary_json = {
        st: {"stocks": len(v["stocks"]), "rows": v["rows"]}
        for st, v in summary.items()
    }
    report_path = os.path.join(report_dir, "cleaning_run_summary.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, ensure_ascii=False, indent=2)
    print(f"Summary written to {report_path}")


def main() -> int:
    p = argparse.ArgumentParser(description="Sina→RDS cleaning pipeline")
    p.add_argument("--stocks", nargs="+", default=["000001", "600000"])
    p.add_argument("--years", nargs="+", required=True)
    p.add_argument("--cache-dir", default=DEFAULT_CACHE)
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    p.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    args = p.parse_args()

    run_pipeline(
        stocks=args.stocks,
        years=_parse_years(args.years),
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
        report_dir=args.report_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())