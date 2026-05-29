#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量下载AKShare(新浪财经)财务数据，用于规则优化。
下载范围: RDS中200只大市值股票 × 2020-2022年 × 全部报告期
"""
import sys, os, json, warnings, time
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from astock_fundamentals.sources.api.akshare_provider import AKShareProvider

CACHE_DIR = os.path.join("data", "akshare_bulk")
STOCK_LIST = os.path.join(CACHE_DIR, "stock_list.csv")
PROGRESS_FILE = os.path.join(CACHE_DIR, "download_progress.json")
os.makedirs(CACHE_DIR, exist_ok=True)

import pandas as pd
stocks = pd.read_csv(STOCK_LIST)

provider = AKShareProvider()

# Load/download progress
progress = {}
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r") as f:
        progress = json.load(f)

STATEMENTS = ["balance_sheet", "income_statement", "cash_flow"]
total = len(stocks) * len(STATEMENTS)
done = 0

for idx, row in stocks.iterrows():
    code = str(row['SECCODE']).zfill(6)
    name = row['SECNAME']

    for st in STATEMENTS:
        key = f"{code}_{st}"
        if key in progress and progress[key].get("status") == "done":
            done += 1
            continue

        # Download (Sina API returns ALL periods in one call)
        try:
            data = None
            for attempt in range(3):
                try:
                    data = provider._get_data_sina(code, 2020, st, "annual")
                    if data and len(data) > 2:
                        break
                    time.sleep(3)
                except Exception:
                    time.sleep(3)

            if data:
                # Save per-stock/statement
                out_path = os.path.join(CACHE_DIR, f"{code}_{st}.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                progress[key] = {"status": "done", "items": len(data)}
                print(f"[{done+1}/{total}] {code} {name} {st}: {len(data)} items ✅")
            else:
                progress[key] = {"status": "failed"}
                print(f"[{done+1}/{total}] {code} {name} {st}: FAILED ❌")
        except Exception as e:
            progress[key] = {"status": "error", "msg": str(e)}
            print(f"[{done+1}/{total}] {code} {name} {st}: ERROR {e}")

        done += 1
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress, f)
        time.sleep(2)  # Rate limiting

print(f"\nDone! {sum(1 for v in progress.values() if v.get('status')=='done')}/{total} successful")
