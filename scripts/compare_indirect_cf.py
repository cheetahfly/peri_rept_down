#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compare downloaded indirect CF data against RDS ground truth.

Usage:
    python scripts/compare_indirect_cf.py --sample 100

Outputs match rate and value accuracy for indirect CF fields.
"""

import os
import sys
import argparse
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.sources.rds.rds_loader import RdsLoader

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDIRECT_DIR = os.path.join(BASE, "data", "exports_v2", "indirect_cf")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")

# Map Sina field names to RDS column names
SINA_TO_RDS = {
    "净利润": "净利润",
    "资产减值准备": "加：资产减值准备",
    "固定资产折旧": "固定资产折旧、油气资产折耗、生产性生物资产折旧",
    "无形资产摊销": "无形资产摊销",
    "长期待摊费用摊销": "长期待摊费用摊销",
    "处置固定资产损失": "处置固定资产、无形资产和其他长期资产的损失",
    "固定资产报废损失": "固定资产报废损失",
    "公允价值变动损失": "公允价值变动损失",
    "投资损失": "投资损失",
    "递延所得税资产减少": "递延所得税资产减少",
    "递延所得税负债增加": "递延所得税负债增加",
    "存货的减少": "存货的减少",
    "经营性应收项目的减少": "经营性应收项目的减少",
    "经营性应付项目的增加": "经营性应付项目的增加",
}


def load_sina_data(stock_code: str) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Load Sina indirect CF data for a stock.
    Returns {field_name: {year: value}}"""
    path = os.path.join(INDIRECT_DIR, f"{stock_code}.csv")
    if not os.path.exists(path):
        return {}
    import pandas as pd
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"stock_code": str})
    result: Dict[str, Dict[int, float]] = {}
    for _, row in df.iterrows():
        name = row["field_name"]
        year = int(row["year"])
        value = float(row["value"])
        result.setdefault(name, {})[year] = value
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sample", type=int, default=100, help="Number of stocks to sample")
    args = p.parse_args()

    rds = RdsLoader(RDS_DIR, decode_map_path=DECODE_PATH)

    # Get list of stocks with indirectly CF data
    stocks = sorted(os.listdir(INDIRECT_DIR))
    if not stocks:
        print("No indirect CF data found. Run download_indirect_cf.py first.")
        return 1

    sample = [s.replace(".csv", "") for s in stocks[:args.sample]]
    print(f"Comparing {len(sample)} stocks...")

    total_matched = 0
    total_compared = 0
    total_fields = 0
    results = []

    for stock_code in sample:
        sina_data = load_sina_data(stock_code)
        if not sina_data:
            continue

        for year in [2020, 2021, 2022]:
            rds_data = rds.load_stock_data(stock_code, year, "cash_flow")
            if not rds_data:
                continue

            for field_name, field_values in sina_data.items():
                if year not in field_values:
                    continue
                sina_val = field_values[year]
                rds_name = SINA_TO_RDS.get(field_name)
                if not rds_name or rds_name not in rds_data:
                    total_fields += 1
                    continue

                rds_val = rds_data[rds_name]
                total_fields += 1
                total_compared += 1

                if rds_val != 0:
                    error_pct = abs(sina_val - rds_val) / abs(rds_val) * 100
                else:
                    error_pct = 0 if abs(sina_val) < 0.01 else float("inf")

                if error_pct < 10:  # within 10% tolerance
                    total_matched += 1

                results.append({
                    "stock": stock_code,
                    "year": year,
                    "field": field_name,
                    "sina": sina_val,
                    "rds": rds_val,
                    "error_pct": error_pct,
                })

    # Summary
    total_results = len(results)
    match_rate = total_matched / total_compared if total_compared else 0
    field_match_rates = {}
    for r in results:
        field_match_rates.setdefault(r["field"], {"matched": 0, "total": 0})
        field_match_rates[r["field"]]["total"] += 1
        if r["error_pct"] < 10:
            field_match_rates[r["field"]]["matched"] += 1

    print(f"\n=== 间接法 CF 对比报告 ===")
    print(f"样本股票数: {len(sample)}")
    print(f"对比字段数: {total_compared}")
    print(f"总字段数: {total_fields}")
    print(f"匹配率 (误差<10%): {match_rate*100:.2f}%")
    print(f"值准确率: {total_matched}/{total_compared}")
    print()

    print("各字段匹配率:")
    for field, stats in sorted(field_match_rates.items()):
        rate = stats["matched"] / stats["total"] * 100 if stats["total"] else 0
        print(f"  {field}: {rate:.1f}% ({stats['matched']}/{stats['total']})")

    # Show worst mismatches
    print("\n最大差异对 (top 10):")
    sorted_results = sorted(results, key=lambda x: -x["error_pct"])
    for r in sorted_results[:10]:
        if r["error_pct"] > 100:
            print(f"  {r['stock']}/{r['year']} {r['field']}: Sina={r['sina']:.2f} RDS={r['rds']:.2f} ({r['error_pct']:.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
