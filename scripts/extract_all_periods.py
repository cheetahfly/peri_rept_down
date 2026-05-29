#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从已缓存的新浪数据中提取 2020-2022 年全部报告期数据。
每个JSON文件包含多年全部报告期，本脚本提取所需部分并与RDS对比。
"""
import sys, os, json, warnings, glob
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
from datetime import datetime
from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.ground_truth.comparator import compare_stock, _compare_values
from astock_fundamentals.core.extraction_config import get_aliases

CACHE_DIR = os.path.join("data", "akshare_bulk")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join("data", "decode_mappings_by_type.json")
OUTPUT_HTML = os.path.join("data", "ground_truth_reports", "full_period_comparison.html")

with open(DECODE_PATH, "r", encoding="utf-8") as f:
    decode_maps = json.load(f)
loader = RdsLoader(RDS_DIR)

# Report types mapping
PERIOD_SUFFIX = {"1231": "annual", "0630": "half", "0331": "q1", "0930": "q3"}
STATEMENTS = [("balance_sheet","BS","b_o.rds"), ("income_statement","IS","pl_o.rds"), ("cash_flow","CF","cf_o.rds")]

# Build RDS index: what data is available per stock/year/period/statement
import pyreadr
rds_index = {}  # {(code, year, period, st): True}

import pandas as pd
for st, st_lbl, fname in STATEMENTS:
    df = pyreadr.read_r(os.path.join(RDS_DIR, fname))[None]
    for _, row in df.iterrows():
        code = str(row['SECCODE']).zfill(6)
        end = str(row['ENDDATE'])[:10] if pd.notna(row['ENDDATE']) else ""
        if len(end) < 10:
            continue
        year = end[:4]
        mmdd = end[5:]
        if mmdd in PERIOD_SUFFIX:
            rds_index[(code, year, mmdd, st)] = True

print(f"RDS index: {len(rds_index)} entries")

# Scan cached Sina files
results = []
processed = 0
stocks_with_data = set()

for fpath in sorted(glob.glob(os.path.join(CACHE_DIR, "*_*.json"))):
    fname = os.path.basename(fpath).replace(".json", "")
    if "_" not in fname or any(x in fname for x in ["stock_list", "download"]):
        continue
    code, st = fname.split("_", 1)
    if st not in ["balance_sheet", "income_statement", "cash_flow"]:
        continue
    if code not in stocks_with_data:
        stocks_with_data.add(code)

    with open(fpath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # raw is a dict {item_name: value} for DEFAULT period (2020 annual)
    # But we saved the data using _get_data_sina which extracts one period only
    # Let's check if we have the RAW dataframe or the extracted dict
    if isinstance(raw, dict):
        # Extract individual items -> we lost multi-period info in the saved format
        # Need to re-download to get multi-period
        pass

print(f"\nSina data: {len(stocks_with_data)} stocks, {len(glob.glob(os.path.join(CACHE_DIR, '*_*.json')))} files")
print(f"\nNOTE: The cached files only contain SINGLE period data. Need to re-download with multi-period support.")
