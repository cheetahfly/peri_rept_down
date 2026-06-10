#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M1: Sample 200 A-share stocks (50 from each of 4 boards) for EM evaluation.

Usage:
    python scripts/eval_em_sample.py --seed 42

Output:
    data/exports_v2/em_evaluation/sample_200.json
"""
import argparse
import json
import os
import sys
from datetime import datetime

# Ensure project root is on path so scripts/eval_em_lib is importable
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import stratified_sample  # noqa: E402

BASE = _PROJECT_ROOT
STOCK_LIST = os.path.join(BASE, "data", "stock_list.json")
OUTPUT_PATH = os.path.join(BASE, "data", "exports_v2", "em_evaluation", "sample_200.json")


def load_full_stock_list() -> list:
    """Load stock codes from data/stock_list.json.

    Each entry is {stockCode, securityName, orgId}. We extract stockCode.
    """
    with open(STOCK_LIST, "r", encoding="utf-8") as f:
        data = json.load(f)
    codes = []
    for item in data:
        code = item.get("stockCode") or item.get("code")
        if code:
            codes.append(str(code).zfill(6))
    return codes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    p.add_argument("--per-board", type=int, default=50, help="Per board sample size (default 50)")
    args = p.parse_args()

    if not os.path.exists(STOCK_LIST):
        print(f"ERROR: Stock list not found: {STOCK_LIST}")
        return 1

    stock_list = load_full_stock_list()
    print(f"Loaded {len(stock_list)} stocks from {STOCK_LIST}")

    result = stratified_sample(stock_list, per_board=args.per_board, seed=args.seed)
    result["generated_at"] = datetime.now().isoformat(timespec="seconds")
    result["source_stock_list"] = STOCK_LIST

    # Print summary
    print(f"\nSampled {args.per_board} from each board (seed={args.seed}):")
    for board, codes in result["boards"].items():
        print(f"  {board:10s}: {len(codes):3d} stocks  (samples: {codes[:3]}...)")
    print(f"  TOTAL      : {len(result['all_codes']):3d} stocks")

    # Save
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())