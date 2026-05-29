#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量下载AKShare(新浪财经)财务数据 - 全覆盖版

策略:
  1. 先快速探测: 若股票不在新浪数据库中则标记并跳过 (不重试)
  2. 有数据的股票: 下载全部3张报表
  3. 支持断点续传
"""
import sys, os, json, warnings, time
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from astock_fundamentals.sources.api.akshare_provider import AKShareProvider

CACHE_DIR = os.path.join("data", "akshare_bulk")
STOCK_LIST_FILE = os.path.join(CACHE_DIR, "stock_list.csv")
PROGRESS_FILE = os.path.join(CACHE_DIR, "download_progress.json")
os.makedirs(CACHE_DIR, exist_ok=True)

stocks = pd.read_csv(STOCK_LIST_FILE)
provider = AKShareProvider()

# Load progress
progress = {}
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r") as f:
        progress = json.load(f)

STATEMENTS = ["balance_sheet", "income_statement", "cash_flow"]
total = len(stocks)
done_count = sum(1 for k, v in progress.items() if v.get("status") == "done")
skip_count = sum(1 for k, v in progress.items() if v.get("status") == "no_data")
print(f"Total: {total} stocks | Already done: {done_count} | No data: {skip_count}")

processed = 0
for idx, row in stocks.iterrows():
    code = str(row['SECCODE']).zfill(6)
    name = str(row['SECNAME'])

    # Check if any statement already done -> skip stock entirely
    all_done = all(progress.get(f"{code}_{st}", {}).get("status") == "done" for st in STATEMENTS)
    any_no_data = any(progress.get(f"{code}_{st}", {}).get("status") == "no_data" for st in STATEMENTS)
    if all_done or any_no_data:
        processed += 1
        continue

    # Try BS as probe (fast: 1 attempt, no retry)
    bs_data = None
    try:
        bs_data = provider._get_data_sina(code, 2020, "balance_sheet", "annual")
    except:
        pass

    if not bs_data or len(bs_data) <= 2:
        # Stock not on Sina
        for st in STATEMENTS:
            progress[f"{code}_{st}"] = {"status": "no_data"}
        processed += 1
        print(f"[{processed}/{total}] {code} {name}: NOT on Sina")
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress, f)
        continue

    # Stock has data - download all 3 statements
    time.sleep(1.5)  # Rate limit between stocks (not between statements - use cached session)
    for st in STATEMENTS:
        key = f"{code}_{st}"
        if progress.get(key, {}).get("status") == "done":
            continue

        data = None
        try:
            if st == "balance_sheet":
                data = bs_data  # Already fetched
            else:
                data = provider._get_data_sina(code, 2020, st, "annual")
        except:
            pass

        if data and len(data) > 2:
            out_path = os.path.join(CACHE_DIR, f"{code}_{st}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            progress[key] = {"status": "done", "items": len(data)}
        else:
            progress[key] = {"status": "no_data"}

        processed += 1
        print(f"[{processed}/{total}] {code} {name} {st}: {len(data) if data else 0} items")
        time.sleep(1.5)

    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)

# Summary
done = sum(1 for v in progress.values() if v.get("status") == "done")
no_data = sum(1 for v in progress.values() if v.get("status") == "no_data")
print(f"\nFinal: {done} done, {no_data} no_data, {len(progress)} total")
