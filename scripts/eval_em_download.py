#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M2: Download EM data for 200 sampled stocks (4 periods × 3 statements).

Usage:
    python scripts/eval_em_download.py [--limit N] [--year 2022]

Output:
    data/exports_v2/em_evaluation/balance_sheet/{code}.csv
    data/exports_v2/em_evaluation/income_statement/{code}.csv
    data/exports_v2/em_evaluation/cash_flow/{code}.csv
    data/exports_v2/em_evaluation/download_progress.json
    data/exports_v2/em_evaluation/download.log
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import (  # noqa: E402
    fetch_em_balance_sheet,
    fetch_em_income_statement,
    fetch_em_cash_flow,
    parse_to_tidy,
    load_field_map,
    EM_API_REQUEST_DELAY,
)

BASE = _PROJECT_ROOT
SAMPLE_PATH = os.path.join(BASE, "data", "exports_v2", "em_evaluation", "sample_200.json")
OUTPUT_ROOT = os.path.join(BASE, "data", "exports_v2", "em_evaluation")
PROGRESS_PATH = os.path.join(OUTPUT_ROOT, "download_progress.json")
LOG_PATH = os.path.join(OUTPUT_ROOT, "download.log")
YEAR = 2022

STATEMENT_TYPES = [
    ("balance_sheet", fetch_em_balance_sheet),
    ("income_statement", fetch_em_income_statement),
    ("cash_flow", fetch_em_cash_flow),
]


def log(msg: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def load_progress() -> dict:
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress: dict) -> None:
    tmp = PROGRESS_PATH + ".tmp"
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    if os.path.exists(PROGRESS_PATH):
        os.remove(PROGRESS_PATH)
    os.rename(tmp, PROGRESS_PATH)


def process_stock(stock_code: str, progress: dict) -> None:
    """Process one stock: fetch all 3 statements, save to CSV."""
    for stmt_type, fetch_func in STATEMENT_TYPES:
        out_dir = os.path.join(OUTPUT_ROOT, stmt_type)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{stock_code}.csv")

        if progress.get(f"{stock_code}|{stmt_type}") in ("done", "no_data"):
            continue

        df = fetch_func(stock_code)
        if df is None or len(df) == 0:
            progress[f"{stock_code}|{stmt_type}"] = "no_data"
            log(f"  {stock_code}/{stmt_type}: no_data")
            continue

        field_map = load_field_map(stmt_type)
        if not field_map:
            log(f"  {stock_code}/{stmt_type}: no field map")
            progress[f"{stock_code}|{stmt_type}"] = "no_data"
            continue

        tidy = parse_to_tidy(df, stock_code, YEAR, field_map, stmt_type, source="em")
        if len(tidy) == 0:
            progress[f"{stock_code}|{stmt_type}"] = "no_data"
            log(f"  {stock_code}/{stmt_type}: no rows after parse")
            continue

        tidy.to_csv(out_path, index=False, encoding="utf-8-sig")
        progress[f"{stock_code}|{stmt_type}"] = "done"
        log(f"  {stock_code}/{stmt_type}: {len(tidy)} rows saved")
        time.sleep(EM_API_REQUEST_DELAY)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None, help="Limit to first N stocks (for testing)")
    p.add_argument("--year", type=int, default=YEAR, help=f"Year (default {YEAR})")
    args = p.parse_args()

    if not os.path.exists(SAMPLE_PATH):
        print(f"ERROR: Sample not found: {SAMPLE_PATH}. Run eval_em_sample.py first.")
        return 1

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        sample = json.load(f)
    codes = sample["all_codes"]
    if args.limit:
        codes = codes[:args.limit]
    print(f"Processing {len(codes)} stocks for year {args.year}...")

    progress = load_progress()

    for i, code in enumerate(codes):
        process_stock(code, progress)
        save_progress(progress)
        if (i + 1) % 10 == 0:
            done = sum(1 for v in progress.values() if v == "done")
            no_data = sum(1 for v in progress.values() if v == "no_data")
            print(f"  [{i + 1}/{len(codes)}] {code}: done={done}, no_data={no_data}")

    done = sum(1 for v in progress.values() if v == "done")
    no_data = sum(1 for v in progress.values() if v == "no_data")
    failed = sum(1 for v in progress.values() if v == "failed")
    print(f"\nFinal: done={done}, no_data={no_data}, failed={failed}")
    print(f"Log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())