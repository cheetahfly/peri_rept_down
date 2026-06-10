#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M3: Check download completeness for the 200-stock sample.

Usage:
    python scripts/eval_em_completeness.py

Output:
    data/exports_v2/em_evaluation/completeness.json
"""
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import check_completeness  # noqa: E402

BASE = _PROJECT_ROOT
SAMPLE_PATH = os.path.join(BASE, "data", "exports_v2", "em_evaluation", "sample_200.json")
OUTPUT_ROOT = os.path.join(BASE, "data", "exports_v2", "em_evaluation")
REPORT_PATH = os.path.join(OUTPUT_ROOT, "completeness.json")


def main() -> int:
    if not os.path.exists(SAMPLE_PATH):
        print(f"ERROR: Sample not found: {SAMPLE_PATH}")
        return 1

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        sample = json.load(f)

    result = check_completeness(sample, OUTPUT_ROOT)

    print(f"\n=== 完整性检查报告 ===")
    print(f"总样本: {result['total_stocks']} 只")
    print(f"有数据: {result['stocks_with_data']} 只 ({result['coverage_rate'] * 100:.1f}%)")
    print(f"完整 (3表齐全): {result['complete_stocks']} 只 ({result['completeness_rate'] * 100:.1f}%)")
    print()
    print("分板块:")
    for board, stats in result["per_board"].items():
        print(f"  {board:10s}: total={stats['total']:3d}  with_data={stats['with_data']:3d}  complete={stats['complete']:3d}")
    print()
    print("分表:")
    for stmt, count in result["per_statement"].items():
        print(f"  {stmt:20s}: {count:3d} 只")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())