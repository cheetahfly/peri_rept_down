#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M4: Compare EM data against RDS ground truth for 200 stocks × 4 periods × 3 statements.

Usage:
    python scripts/eval_em_compare_rds.py

Output:
    data/exports_v2/em_evaluation/compare_rds_report.json
"""
import json
import os
import sys
from collections import Counter

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import compare_em_rds_batch  # noqa: E402

sys.path.insert(0, _PROJECT_ROOT)
from astock_fundamentals.sources.rds.rds_loader import RdsLoader  # noqa: E402

BASE = _PROJECT_ROOT
SAMPLE_PATH = os.path.join(BASE, "data", "exports_v2", "em_evaluation", "sample_200.json")
OUTPUT_ROOT = os.path.join(BASE, "data", "exports_v2", "em_evaluation")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
REPORT_PATH = os.path.join(OUTPUT_ROOT, "compare_rds_report.json")


def main() -> int:
    if not os.path.exists(SAMPLE_PATH):
        print(f"ERROR: Sample not found: {SAMPLE_PATH}")
        return 1

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        sample = json.load(f)

    print("Loading RDS data...")
    rds = RdsLoader(RDS_DIR, decode_map_path=DECODE_PATH)
    print(f"  Loaded RDS from {RDS_DIR}")

    print(f"Comparing {len(sample['all_codes'])} stocks × 4 periods × 3 statements...")
    result = compare_em_rds_batch(sample, rds, OUTPUT_ROOT, year=2022)

    s = result["summary"]
    print(f"\n=== EM vs RDS 比对报告 ===")
    print(f"总比对数: {s['total_comparisons']} (股票×期次×报表)")
    print(f"匹配字段: {s['total_matched']}/{s['total_common_fields']} ({s['overall_match_rate'] * 100:.2f}%)")
    print()
    print("分表:")
    for stmt, stats in result["per_statement"].items():
        rate = stats["matched"] / stats["common"] * 100 if stats["common"] else 0
        print(f"  {stmt:20s}: {stats['matched']:5d}/{stats['common']:5d} ({rate:.1f}%)")
    print()
    print("分板块:")
    for board, stats in result["per_board"].items():
        rate = stats["matched"] / stats["common"] * 100 if stats["common"] else 0
        print(f"  {board:10s}: {stats['matched']:5d}/{stats['common']:5d} ({rate:.1f}%)  ({stats['stocks']} stocks)")

    print("\n最大差异对 Top 10:")
    all_anomalies = []
    for r in result["per_stock"]:
        for a in r["anomalies"]:
            all_anomalies.append((a["diff"], r["stock_code"], r["statement_type"], r["period"], a))
    all_anomalies.sort(reverse=True)
    for diff, stock, stmt, period, a in all_anomalies[:10]:
        print(f"  {stock}/{stmt}/{period} {a['field']}: EM={a['em']:.2f} RDS={a['rds']:.2f} 差={diff:.2f}元")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSaved to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())