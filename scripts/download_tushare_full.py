# -*- coding: utf-8 -*-
"""
5,000 只 A 股全量 tushare 拉取脚本（拿到 token 后手动跑）。

用法：
  export TUSHARE_TOKEN=your_token
  python scripts/download_tushare_full.py --years 2020-2022

输出：
  data/exports_v2/tushare_full/{ts_code}_{year}_{stmt_type}.csv
  data/tushare_full_checkpoint.json（断点续传）

速率：每只股 × 3 表 × sleep 0.4s = ~1.2s/股；5K × 3 年 = ~5h
"""
import argparse
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from astock_fundamentals.sources.api import TushareProvider  # noqa: E402

OUT_DIR = "data/exports_v2/tushare_full"
CHECKPOINT_PATH = "data/tushare_full_checkpoint.json"
os.makedirs(OUT_DIR, exist_ok=True)


def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            return set(tuple(x) for x in json.load(f).get("done", []))
    return set()


def save_checkpoint(done):
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump({"done": sorted(list(done))}, f, ensure_ascii=False, indent=2)


def get_stock_list():
    """获取 A 股全量股票清单（用 akshare）"""
    import akshare as ak
    df = ak.stock_zh_a_spot_em()
    return df["代码"].astype(str).tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2020-2022", help="year range, e.g. 2020-2022")
    ap.add_argument("--resume", action="store_true", help="resume from checkpoint")
    ap.add_argument("--rate-limit-sleep", type=float, default=0.4)
    args = ap.parse_args()

    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        sys.exit("ERROR: TUSHARE_TOKEN env required")

    years = list(range(int(args.years.split("-")[0]),
                       int(args.years.split("-")[1]) + 1))
    stocks = get_stock_list()
    provider = TushareProvider(token=token, rate_limit_sleep=args.rate_limit_sleep)
    done = load_checkpoint() if args.resume else set()
    print(f"Total stocks: {len(stocks)}, years: {years}, done: {len(done)}")

    stmt_methods = [
        ("balance_sheet", provider.get_balance_sheet),
        ("income_statement", provider.get_income_statement),
        ("cash_flow", provider.get_cash_flow),
    ]

    success = 0
    failed = 0
    skipped = 0
    for i, stock in enumerate(stocks):
        ts_code = TushareProvider._ts_code(stock)
        for year in years:
            for stmt_type, get_fn in stmt_methods:
                key = (stock, str(year), stmt_type)
                if key in done:
                    skipped += 1
                    continue
                try:
                    data = get_fn(stock, year)
                except Exception as e:
                    failed += 1
                    done.add(key)
                    continue
                if data:
                    df = pd.DataFrame(list(data.items()), columns=["item", "value"])
                    df.insert(0, "ts_code", ts_code)
                    df.insert(1, "year", year)
                    df.insert(2, "statement_type", stmt_type)
                    out_path = os.path.join(OUT_DIR, f"{ts_code}_{year}_{stmt_type}.csv")
                    df.to_csv(out_path, index=False, encoding="utf-8-sig")
                    success += 1
                done.add(key)

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(stocks)}, success={success}, failed={failed}, skipped={skipped}")
            save_checkpoint(done)

    save_checkpoint(done)
    print(f"\nDone: {success} success, {failed} failed, {skipped} skipped")


if __name__ == "__main__":
    main()
