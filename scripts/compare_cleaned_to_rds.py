#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compare cleaned Sina Tidy CSV to RDS ground truth, report match rate + value accuracy.

Optimized: pre-loads each RDS .rds file once, builds (stock_code, year) -> dict
index, then iterates Tidy CSV in memory.
"""

import json
import os
import sys
from typing import Dict

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.sources.rds.rds_loader import RdsLoader

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tmp = "/tmp/full_pipeline_v2"
if not os.path.exists(_tmp):
    _tmp = os.path.expanduser("~/AppData/Local/Temp/full_pipeline_v2")
INPUT_DIR = _tmp
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
OUTPUT = os.path.join(BASE, "data", "ground_truth_reports", "cleaned_vs_rds_200stocks.json")

STATEMENT_TYPES = ["balance_sheet", "income_statement", "cash_flow"]


def _load_decode_map(path: str) -> Dict[str, Dict[str, str]]:
    for enc in ("utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except UnicodeDecodeError:
            continue
    with open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8", errors="replace"))


def _build_rds_index(rds: RdsLoader, statement_type: str, decode_for_st: Dict[str, str]):
    """Build {(stock_code, year): {chinese_name: value}} for one statement type.

    Loads BOTH financial and non-financial .rds files and merges by (stock, year).
    Financial file takes precedence for financial stocks.
    """
    # Use _o.rds as non-financial and _f.rds as financial (per RdsLoader convention)
    table_map_nonfin = {
        "balance_sheet": "b_o.rds",
        "income_statement": "pl_o.rds",
        "cash_flow": "cf_o.rds",
    }
    table_map_fin = {
        "balance_sheet": "b_f.rds",
        "income_statement": "pl_f.rds",
        "cash_flow": "cf_f.rds",
    }
    fn_nonfin = table_map_nonfin.get(statement_type)
    fn_fin = table_map_fin.get(statement_type)

    # Load both .rds files
    frames = []
    for fn in (fn_nonfin, fn_fin):
        if fn:
            try:
                df = rds._load_rds(fn)
                if df is not None and len(df) > 0:
                    frames.append(df)
            except Exception as e:
                print(f"  WARN: failed to load {fn}: {e}", flush=True)
    if not frames:
        return {}

    # Concatenate (financial records appended, will be deduped by (stock, year))
    df = pd.concat(frames, ignore_index=True)

    # Pre-filter decode columns (F-code columns only)
    decode_cols = [c for c in df.columns if c in decode_for_st]
    if "SECCODE" not in df.columns or "ENDDATE" not in df.columns:
        return {}

    # Build index. If duplicates, prefer records that are NOT NaN.
    index: Dict[tuple, Dict[str, float]] = {}
    df_year = df["ENDDATE"].astype(str).str[:4]
    for stock_code, year, row in zip(df["SECCODE"], df_year, df[decode_cols].itertuples(index=False, name=None)):
        if pd.isna(stock_code) or pd.isna(year):
            continue
        try:
            y = int(year)
        except (ValueError, TypeError):
            continue
        key = (stock_code, y)
        # Build row dict
        new_data = {}
        has_value = False
        for col, val in zip(decode_cols, row):
            if val is not None and str(val) != "nan":
                try:
                    new_data[decode_for_st[col]] = float(val)
                    has_value = True
                except (ValueError, TypeError):
                    pass
        if not has_value:
            continue
        # Merge: if existing has more fields, keep existing; else use new
        if key not in index or len(new_data) > len(index[key]):
            index[key] = new_data
    return index


def main():
    # Load Tidy CSVs
    tidy_by_stmt: Dict[str, pd.DataFrame] = {}
    for st in STATEMENT_TYPES:
        path = os.path.join(INPUT_DIR, f"sina_cleaned_{st}.csv")
        if not os.path.exists(path):
            print(f"WARN: {path} not found, skipping {st}", flush=True)
            continue
        df = pd.read_csv(path, encoding="utf-8-sig", dtype={"stock_code": str})
        tidy_by_stmt[st] = df
        print(f"Loaded {len(df)} rows from {path}", flush=True)

    # Load RDS
    rds = RdsLoader(RDS_DIR, decode_map_path=DECODE_PATH)
    decode_maps = _load_decode_map(DECODE_PATH)
    print("RdsLoader initialized", flush=True)

    # Pre-build RDS index per statement (this is the slow part - done once)
    rds_index: Dict[str, Dict[tuple, Dict[str, float]]] = {}
    for st in STATEMENT_TYPES:
        decode_for_st = decode_maps.get(st, {})
        print(f"Building RDS index for {st} ({len(decode_for_st)} field codes)...", flush=True)
        idx = _build_rds_index(rds, st, decode_for_st)
        rds_index[st] = idx
        print(f"  {st}: {len(idx)} (stock, year) cells indexed", flush=True)

    # Compare per (stock, year, statement) cell
    results = []
    for st, df in tidy_by_stmt.items():
        idx = rds_index.get(st, {})
        decode_for_st = decode_maps.get(st, {})

        # Pre-build field_code -> chinese_name
        df = df.copy()
        df["chinese_name"] = df["field_code"].map(decode_for_st)
        df = df.dropna(subset=["chinese_name"])
        print(f"  {st}: {len(df)} rows with known field_code mapping", flush=True)

        # Group by (stock_code, year)
        cells = df.groupby(["stock_code", "year"])
        cell_count = 0
        for (stock_code, year), cell_df in cells:
            rds_data = idx.get((stock_code, int(year)))
            if not rds_data:
                continue
            cell_count += 1

            cell_matches = 0
            cell_total = 0
            cell_value_diffs = 0
            sina_values = cell_df["value"].astype(float).values
            chinese_names = cell_df["chinese_name"].values
            for sina_v, cn in zip(sina_values, chinese_names):
                rds_v = rds_data.get(cn)
                if rds_v is None:
                    cell_total += 1
                    continue
                cell_total += 1
                if abs(float(sina_v) - float(rds_v)) < 0.01:
                    cell_matches += 1
                else:
                    cell_value_diffs += 1

            if cell_total > 0:
                results.append({
                    "stock_code": stock_code,
                    "year": int(year),
                    "statement_type": st,
                    "total_fields": cell_total,
                    "matched": cell_matches,
                    "value_diffs": cell_value_diffs,
                    "match_rate": cell_matches / cell_total if cell_total else 0,
                })
        print(f"  {st} done: {cell_count} cells compared", flush=True)

    # Aggregate
    by_stmt: Dict[str, dict] = {}
    for r in results:
        k = r["statement_type"]
        by_stmt.setdefault(k, {"comparisons": 0, "total_fields": 0, "matched": 0, "value_diffs": 0})
        by_stmt[k]["comparisons"] += 1
        by_stmt[k]["total_fields"] += r["total_fields"]
        by_stmt[k]["matched"] += r["matched"]
        by_stmt[k]["value_diffs"] += r["value_diffs"]

    summary = {
        "scope": f"{len(set(r['stock_code'] for r in results))} stocks x {len(set(r['year'] for r in results))} years x {len(STATEMENT_TYPES)} statements",
        "source": "sina_cleaned_*.csv from clean_sina_pipeline.py (P0-1a fixed)",
        "total_comparisons": len(results),
        "by_statement": {
            k: {
                "comparisons": v["comparisons"],
                "total_fields": v["total_fields"],
                "matched": v["matched"],
                "value_diffs": v["value_diffs"],
                "match_rate": round(v["matched"] / v["total_fields"], 4) if v["total_fields"] else 0,
            } for k, v in by_stmt.items()
        },
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
