#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download indirect cash flow data from Sina (AKShare) for all A-share stocks.

Outputs per-stock Tidy CSV to data/exports_v2/indirect_cf/{code}.csv.
Supports resume via progress.json checkpoint file.

Usage:
    python scripts/download_indirect_cf.py
"""

import os
import sys
import json
import time
import warnings
from typing import Dict, List, Optional

warnings.filterwarnings("ignore")

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK_LIST = os.path.join(BASE, "data", "ground_truth_reports", "full_stock_list.txt")
OUTPUT_DIR = os.path.join(BASE, "data", "exports_v2", "indirect_cf")
PROGRESS_FILE = os.path.join(BASE, "data", "ground_truth_reports", "indirect_cf_progress.json")
LOG_FILE = os.path.join(BASE, "data", "ground_truth_reports", "indirect_cf_download.log")

# Years to download (annual reports only)
YEARS = [2020, 2021, 2022]

# Column index → (F-code, display_order, chinese_name)
# NOTE: F123N-F137N used instead of F057N-F071N to avoid duplicate keys
INDIRECT_FIELDS = {
    47: ("F123N", 85, "净利润"),
    48: ("F124N", 86, "资产减值准备"),
    49: ("F125N", 87, "固定资产折旧"),
    50: ("F126N", 88, "无形资产摊销"),
    51: ("F127N", 89, "长期待摊费用摊销"),
    52: ("F128N", 90, "处置固定资产损失"),
    53: ("F129N", 91, "固定资产报废损失"),
    54: ("F130N", 92, "公允价值变动损失"),
    56: ("F131N", 93, "投资损失"),
    57: ("F132N", 94, "递延所得税资产减少"),
    58: ("F133N", 95, "递延所得税负债增加"),
    59: ("F134N", 96, "存货的减少"),
    60: ("F135N", 97, "经营性应收项目的减少"),
    61: ("F136N", 98, "经营性应付项目的增加"),
    62: ("F137N", 99, "其他"),
}

MAX_RETRIES = 3
REQUEST_DELAY = 0.5  # seconds between requests


def load_stocks() -> List[str]:
    """Load stock codes from full_stock_list.txt."""
    with open(STOCK_LIST, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_progress() -> Dict[str, str]:
    """Load progress checkpoint. Returns {stock_code: status}."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress: Dict[str, str]) -> None:
    """Save progress checkpoint atomically."""
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROGRESS_FILE)


def log(message: str) -> None:
    """Append message to log file."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{ts}] {message}\n")


def fetch_indirect_cf(stock_code: str) -> Optional[pd.DataFrame]:
    """Fetch indirect CF data from AKShare with retry logic."""
    import akshare as ak

    for attempt in range(MAX_RETRIES):
        try:
            df = ak.stock_financial_cash_ths(symbol=stock_code)
            time.sleep(REQUEST_DELAY)
            return df
        except Exception as e:
            log(f"  Retry {attempt + 1}/{MAX_RETRIES} for {stock_code}: {e}")
            time.sleep(2 ** attempt)
    log(f"  FAILED after {MAX_RETRIES} retries: {stock_code}")
    return None


def parse_to_tidy(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    """Parse AKShare DataFrame to Tidy format for 2020-2022 annual reports."""
    rows = []
    for _, row in df.iterrows():
        # First column is report date
        report_date = str(row.iloc[0])
        if not report_date.startswith("202"):
            continue
        try:
            year = int(report_date[:4])
        except (ValueError, TypeError):
            continue
        if year not in YEARS:
            continue
        # Only annual reports (12-31)
        if "-12-31" not in report_date:
            continue

        for col_idx, (fcode, order, name) in INDIRECT_FIELDS.items():
            if col_idx >= len(df.columns):
                continue
            val = row.iloc[col_idx]
            if val is None or str(val) == "False" or str(val) == "nan":
                continue
            try:
                fvalue = float(val)
            except (ValueError, TypeError):
                continue
            rows.append({
                "stock_code": stock_code,
                "year": year,
                "period": "annual",
                "statement_type": "cash_flow",
                "field_code": fcode,
                "field_name": name,
                "value": fvalue,
                "display_order": order,
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    # Smoke test
    stocks = load_stocks()
    print(f"Loaded {len(stocks)} stocks")
    print(f"INDIRECT_FIELDS has {len(INDIRECT_FIELDS)} entries")
    print(f"Output dir: {OUTPUT_DIR}")
