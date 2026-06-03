#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对比新浪财经数据与RDS标准数据，总结经验并归纳规则。

策略:
1. 使用之前下载的Sina数据（不再重新下载）
2. 加载RDS数据进行对比
3. 使用已有的compare_stock函数
4. 汇总结果并生成规则
"""

import sys
import os
import json
import glob
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.sources.api.akshare_provider import AKShareProvider
from astock_fundamentals.ground_truth.comparator import compare_stock, ComparisonResult
from astock_fundamentals.core.extraction_config import get_aliases

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE, "..", "data", "akshare_bulk")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "..", "data", "decode_mappings_by_type.json")
OUTPUT_DIR = os.path.join(BASE, "..", "data", "ground_truth_reports")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load config
with open(DECODE_PATH, "r", encoding="utf-8") as f:
    decode_maps = json.load(f)

# Load overlap stocks
with open(os.path.join(CACHE_DIR, "overlap_stocks.json")) as f:
    overlap_stocks = json.load(f)

print(f"Loaded {len(overlap_stocks)} stocks with both Sina + RDS data")

# Initialize loaders
rds_loader = RdsLoader(RDS_DIR)
sina_provider = AKShareProvider()

# Load field order
import yaml
field_order_path = os.path.join(BASE, "..", "rules", "field_order.yaml")
with open(field_order_path, "r", encoding="utf-8") as f:
    field_order = yaml.safe_load(f)

# Comparison results cache
CACHE_FILE = os.path.join(CACHE_DIR, "comparison_results_cache.json")
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        all_results = json.load(f)
    print(f"Loaded {len(all_results)} cached comparison results")
else:
    all_results = []

# Track which stocks we've already compared
compared_keys = set()
for r in all_results:
    compared_keys.add((r["stock"], r["year"], r["statement_type"]))

# Statements to compare
STATEMENTS = ["balance_sheet", "income_statement", "cash_flow"]

# Limit to first 100 stocks for speed (we can expand later)
MAX_STOCKS = 100
stocks_to_compare = overlap_stocks[:MAX_STOCKS]
print(f"Comparing {len(stocks_to_compare)} stocks (limited for speed)")

# Run comparisons
new_comparisons = 0
skipped = 0

for stock_code in stocks_to_compare:
    # Check what periods are available in Sina for this stock
    sina_files = glob.glob(os.path.join(CACHE_DIR, f"{stock_code}_*.csv"))
    if not sina_files:
        continue

    # Extract available years from Sina files
    for st in STATEMENTS:
        csv_path = os.path.join(CACHE_DIR, f"{stock_code}_{st}.csv")
        if not os.path.exists(csv_path):
            continue

        # Get available periods from Sina
        import pandas as pd
        try:
            df = pd.read_csv(csv_path, dtype={0: str})
            periods = df.iloc[:, 0].dropna().unique()
        except Exception:
            continue

        for period in periods:
            # Convert period to year
            if len(str(period)) == 8:
                year = int(str(period)[:4])
            else:
                continue

            # Skip if we've already compared this
            key = (stock_code, str(year), st)
            if key in compared_keys:
                skipped += 1
                continue

            # Get Sina data
            try:
                sina_data = sina_provider._get_data_sina(stock_code, year, st, "annual")
                if not sina_data or len(sina_data) < 2:
                    continue
            except Exception as e:
                continue

            # Get RDS data
            try:
                rds_data = rds_loader.load_stock_data(stock_code, year, st)
                if not rds_data or len(rds_data) < 2:
                    continue
            except Exception as e:
                continue

            # Compare
            try:
                aliases = get_aliases(st, "annual")
                dm = decode_maps.get(st, {})
                comp_result = compare_stock(
                    rds_data, sina_data, aliases,
                    stock_code=stock_code, year=year,
                    statement_type=st, decode_map=dm
                )

                # Save result
                result = {
                    "stock": stock_code,
                    "year": year,
                    "statement_type": st,
                    "summary": comp_result.summary(),
                    "matched_count": len(comp_result.matched),
                    "missing_count": len(comp_result.missing),
                    "unmatched_count": len(comp_result.unmatched),
                }
                all_results.append(result)
                compared_keys.add(key)
                new_comparisons += 1

                # Save progress
                if new_comparisons % 10 == 0:
                    with open(CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump(all_results, f, ensure_ascii=False, indent=2)

            except Exception as e:
                continue

    # Print progress every 10 stocks
    if len([r for r in all_results if r["stock"] == stock_code]) > 0:
        print(f"  Processed {stock_code}: {len([r for r in all_results if r['stock'] == stock_code])} comparisons")

# Save final results
with open(CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

print(f"\nNew comparisons: {new_comparisons}")
print(f"Skipped (already compared): {skipped}")
print(f"Total results: {len(all_results)}")

# Generate summary
summary = {
    "total_comparisons": len(all_results),
    "by_statement": {},
    "by_year": {},
    "match_rates": {},
}

for r in all_results:
    st = r["statement_type"]
    year = r["year"]

    if st not in summary["by_statement"]:
        summary["by_statement"][st] = {"total": 0, "matched": 0}
    summary["by_statement"][st]["total"] += 1
    summary["by_statement"][st]["matched"] += r["matched_count"]

    if year not in summary["by_year"]:
        summary["by_year"][year] = {"total": 0, "matched": 0}
    summary["by_year"][year]["total"] += 1
    summary["by_year"][year]["matched"] += r["matched_count"]

    match_rate = r["matched_count"] / r["gt_items"] if r.get("gt_items", 0) > 0 else 0
    key = f"{st}_{year}"
    if key not in summary["match_rates"]:
        summary["match_rates"][key] = []
    summary["match_rates"][key].append(match_rate)

# Calculate average match rates
for key in summary["match_rates"]:
    rates = summary["match_rates"][key]
    summary["match_rates"][key] = {
        "mean": sum(rates) / len(rates) if rates else 0,
        "count": len(rates),
        "min": min(rates) if rates else 0,
        "max": max(rates) if rates else 0,
    }

print("\n=== Summary ===")
print(json.dumps(summary, indent=2, ensure_ascii=False))

# Save summary
summary_path = os.path.join(OUTPUT_DIR, "sina_vs_rds_summary.json")
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f"\nSaved summary to {summary_path}")
