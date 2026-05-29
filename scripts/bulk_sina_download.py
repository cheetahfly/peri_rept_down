#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量下载AKShare(新浪财经)财务数据 - 多报告期版

保存RAW API数据（全部报告期），支持后续提取任意年份/报告期。
每次运行会增量补充新股票，已有数据自动跳过。

下载的数据包含每只股票完整的多年多期数据（年报+半年报+季报）。
"""
import sys, os, json, warnings, time
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from astock_fundamentals.sources.api.akshare_provider import AKShareProvider

CACHE_DIR = os.path.join("data", "akshare_bulk")
STOCK_LIST = os.path.join(CACHE_DIR, "stock_list.csv")
PROGRESS_FILE = os.path.join(CACHE_DIR, "download_progress.json")
os.makedirs(CACHE_DIR, exist_ok=True)

stocks = pd.read_csv(STOCK_LIST)
provider = AKShareProvider()

progress = {}
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r") as f:
        progress = json.load(f)

STATEMENTS = ["balance_sheet", "income_statement", "cash_flow"]
total = len(stocks)
done_count = sum(1 for v in progress.values() if v.get("status") == "done")
print(f"Total: {total} stocks | Done: {done_count}")

processed = sum(1 for v in progress.values() if v.get("status") in ("done", "no_data"))
for idx, row in stocks.iterrows():
    code = str(row['SECCODE']).zfill(6)
    name = str(row['SECNAME'][:8])

    all_done = all(progress.get(f"{code}_{st}", {}).get("status") == "done" for st in STATEMENTS)
    if all_done:
        continue

    # Probe with BS
    try:
        raw_df = provider._fetch_sina(code, "资产负债表")
    except:
        raw_df = None

    if raw_df is None or raw_df.empty or len(raw_df) < 5:
        for st in STATEMENTS:
            progress[f"{code}_{st}"] = {"status": "no_data"}
        processed += 1
        print(f"[{processed}/{total}] {code} {name}: no data")
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress, f)
        continue

    # Save RAW dataframe as CSV (preserves ALL periods)
    csv_path = os.path.join(CACHE_DIR, f"{code}_raw.csv")
    raw_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    for st, st_label, st_cn in zip(STATEMENTS, ["BS","IS","CF"], ["BS","IS","CF"]):
        key = f"{code}_{st}"
        try:
            df = raw_df if st == "balance_sheet" else provider._fetch_sina(code, {"balance_sheet":"资产负债表","income_statement":"利润表","cash_flow":"现金流量表"}[st])
            if df is not None and len(df) > 5:
                df.to_csv(os.path.join(CACHE_DIR, f"{code}_{st}.csv"), index=False, encoding="utf-8-sig")
                # Also save JSON summary for quick access: {period: {item: value}}
                periods = df.iloc[:, 0].tolist()
                summary = {}
                for i, period in enumerate(periods):
                    row_data = df.iloc[i]
                    items = {}
                    for j in range(1, len(df.columns)):
                        val = row_data.iloc[j]
                        if pd.notna(val):
                            try:
                                items[str(df.columns[j])] = float(val)
                            except (ValueError, TypeError):
                                pass
                    summary[str(period)] = items
                with open(os.path.join(CACHE_DIR, f"{code}_{st}.json"), "w", encoding="utf-8") as f:
                    json.dump(summary, f, ensure_ascii=False)
                progress[key] = {"status": "done", "periods": len(periods)}
            else:
                progress[key] = {"status": "no_data"}
        except:
            progress[key] = {"status": "no_data"}

        processed += 1
        print(f"[{processed}/{total}] {code} {name} {st_label}")
        time.sleep(2)

    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)

done = sum(1 for v in progress.values() if v.get("status") == "done")
print(f"\nFinal: {done} done, {total} total")
