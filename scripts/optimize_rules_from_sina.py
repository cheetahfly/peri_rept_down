#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于新浪下载数据优化匹配规则。
分析值全等但名不同的情况，更新 value_mapping_rules.yaml 和 aliases.yaml。
"""
import sys, os, json, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re, yaml
from collections import defaultdict
from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.ground_truth.comparator import (
    compare_stock, _compare_values, normalize_name, load_value_mapping_rules
)
from astock_fundamentals.core.extraction_config import get_aliases

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE, "..", "data", "akshare_bulk")
RULES_DIR = os.path.join(BASE, "..", "rules")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "..", "data", "decode_mappings_by_type.json")

with open(DECODE_PATH, "r", encoding="utf-8") as f:
    decode_maps = json.load(f)
loader = RdsLoader(RDS_DIR)
existing_rules = load_value_mapping_rules() or {}

# Analyze all downloaded files for value-based matching opportunities
print("Scanning downloaded Sina data for new mapping opportunities...")
new_mappings = defaultdict(list)  # st -> [(rds_name, sina_name, value)]

import glob
files = glob.glob(os.path.join(CACHE_DIR, "*_*.json"))
files = [f for f in files if not f.endswith("stock_list.csv") and not f.endswith("progress.json")]

stocks_done = set()
for fpath in files:
    fname = os.path.basename(fpath)
    parts = fname.replace(".json", "").split("_", 1)
    if len(parts) != 2:
        continue
    code, st = parts[0], parts[1]
    stocks_done.add(code)

    with open(fpath, "r", encoding="utf-8") as f:
        sina = json.load(f)
    try:
        rds = loader.load_stock_data(code, 2020, st)
    except:
        continue
    if not rds or not sina:
        continue

    # Value-based matching
    for rn, rv in rds.items():
        if rv is None or abs(rv) < 1:
            continue
        for sn, sv in sina.items():
            if sv is None or abs(sv) < 1:
                continue
            err = _compare_values(rv, sv)
            if err is not None and err < 0.001:  # Exact value match
                # Different names?
                if normalize_name(rn) != normalize_name(sn):
                    key = (st, rn, sn)
                    new_mappings[key].append(rv)

print(f"Analyzed {len(files)} files for {len(stocks_done)} stocks")
print(f"Found {len(new_mappings)} unique value-matched name pairs")

# Separate "already known" from "new discoveries"
known_pairs = set()
sina_to_rds = existing_rules.get("sina_to_rds", {})
for st, mappings in sina_to_rds.items():
    for m in mappings:
        known_pairs.add((st, m.get("rds", ""), m.get("sina", "")))

known_count = 0
new_count = 0
st_new = defaultdict(list)

for (st, rn, sn), vals in sorted(new_mappings.items(), key=lambda x: -len(x[1])):
    pair = (st, rn, sn)
    if pair in known_pairs:
        known_count += 1
    else:
        new_count += 1
        st_new[st].append((rn, sn, vals[0], len(vals)))
        print(f"  NEW: [{st}] RDS={rn} <-> Sina={sn} (value={vals[0]:,.2f}, seen in {len(vals)} stocks)")

print(f"\nKnown mappings: {known_count}, New discoveries: {new_count}")

# ===== Auto-update value_mapping_rules.yaml =====
if new_count > 0:
    rules_path = os.path.join(RULES_DIR, "value_mapping_rules.yaml")
    with open(rules_path, "r", encoding="utf-8") as f:
        rules_content = f.read()

    # Generate new rule entries
    new_entries = []
    for st, items in sorted(st_new.items()):
        new_entries.append(f"\n  # === Auto-learned at {__import__('datetime').datetime.now().isoformat()[:19]} ===\n")
        for rn, sn, val, count in sorted(items, key=lambda x: -x[3]):
            if count >= 2:  # Only add patterns seen in 2+ stocks
                new_entries.append(f"    - sina: \"{sn}\"\n      rds: \"{rn}\"\n      type: value_exact  # auto (seen in {count} stocks, e.g. {val:,.0f})\n")

    if new_entries:
        # Add before auto_learned_mappings
        marker = "auto_learned_mappings: []"
        replacement = f"auto_learned_mappings:\n" + "".join(new_entries)
        rules_content = rules_content.replace(marker, replacement)
        with open(rules_path, "w", encoding="utf-8") as f:
            f.write(rules_content)
        print(f"\nAdded {len(new_entries)} new rules to {rules_path}")
else:
    print("\nNo new mappings to add")

# ===== Summary report =====
print(f"\n{'='*60}")
print(f"Rule Optimization Summary")
print(f"{'='*60}")
print(f"Stocks analyzed: {len(stocks_done)}")
print(f"Sina files processed: {len(files)}")
print(f"Known name mappings: {known_count}")
print(f"New discoveries: {new_count}")
print(f"Total value-matched pairs: {len(new_mappings)}")
