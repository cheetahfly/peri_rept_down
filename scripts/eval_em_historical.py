#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M5: Re-test historical sina anomalies with EM data.

Scans sina_cleaned_*.csv for |sina - rds| > 1元 fields, then checks if EM matches RDS.

Usage:
    python scripts/eval_em_historical.py

Output:
    data/exports_v2/em_evaluation/historical_issues.json
"""
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import scan_sina_anomalies, recheck_with_em  # noqa: E402

sys.path.insert(0, _PROJECT_ROOT)
from astock_fundamentals.sources.rds.rds_loader import RdsLoader  # noqa: E402

BASE = _PROJECT_ROOT
SINA_CSVS = [
    os.path.join(BASE, "data", "exports_v2", "sina_cleaned_balance_sheet.csv"),
    os.path.join(BASE, "data", "exports_v2", "sina_cleaned_income_statement.csv"),
    os.path.join(BASE, "data", "exports_v2", "sina_cleaned_cash_flow.csv"),
]
OUTPUT_ROOT = os.path.join(BASE, "data", "exports_v2", "em_evaluation")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
REPORT_PATH = os.path.join(OUTPUT_ROOT, "historical_issues.json")


def main() -> int:
    rds = RdsLoader(RDS_DIR, decode_map_path=DECODE_PATH)
    def rds_callable(code, year, stmt):
        return rds.load_stock_data(code, year, stmt) or {}

    all_anomalies = []
    for csv_path in SINA_CSVS:
        if not os.path.exists(csv_path):
            print(f"  WARN: {csv_path} not found, skipping")
            continue
        print(f"Scanning {csv_path}...")
        anomalies = scan_sina_anomalies(csv_path, rds_callable, tolerance=1.0)
        print(f"  Found {len(anomalies)} anomalies")
        all_anomalies.extend(anomalies)

    print(f"\nTotal anomalies: {len(all_anomalies)}")

    if not all_anomalies:
        print("No anomalies to recheck.")
        result = {
            "anomalies_count": 0,
            "em_matched": 0,
            "em_unmatched": 0,
            "em_no_data": 0,
            "match_rate": 0,
            "improvement": 0,
            "details": [],
        }
    else:
        print("Re-checking with EM data...")
        result = recheck_with_em(all_anomalies, OUTPUT_ROOT, tolerance=1.0)

    print(f"\n=== 历史疑难数据 EM 重测 ===")
    print(f"疑难样本数: {result['anomalies_count']}")
    print(f"EM 匹配数: {result['em_matched']}")
    print(f"EM 仍不匹配: {result['em_unmatched']}")
    print(f"EM 无数据: {result['em_no_data']}")
    print(f"EM 匹配率: {result['match_rate'] * 100:.2f}%")
    print(f"EM 改善率 (vs sina 0%): {result['improvement'] * 100:.2f}%")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSaved to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())