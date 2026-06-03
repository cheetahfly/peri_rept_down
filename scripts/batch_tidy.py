#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量生成 Tidy Data 格式输出。

遍历 data/extracted/by_code/ 下的所有股票/年份，对每条提取结果：
1. 加载 RDS ground truth（含 display_order）
2. 运行 Comparator 进行 9 策略匹配
3. 生成 Tidy Data 行（每行：stock_code, year, report_type, statement_type, item_code, item_name, value, display_order, source）
4. 运行 GapAnalyzer 生成差异分析和别名建议

输出：
  data/exports_v2/tidy_data.csv          - 所有匹配的 Tidy Data（RDS ground truth）
  data/exports_v2/tidy_data_extracted.csv - 提取数据转 Tidy Data 格式
  data/ground_truth_reports/tidy_gaps.html - 差异分析报告
"""
import sys, os, json, yaml, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime
from collections import defaultdict
from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.ground_truth.comparator import compare_stock, ComparisonResult
from astock_fundamentals.ground_truth.gap_analyzer import (
    GapAnalyzer, GapSummary, analyze_value_matches, RuleSuggestion
)
from astock_fundamentals.core.extraction_config import get_aliases

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
EXTRACTED_DIR = os.path.join(BASE, "data", "extracted", "by_code")
EXPORT_DIR = os.path.join(BASE, "data", "exports_v2")
REPORT_DIR = os.path.join(BASE, "data", "ground_truth_reports")
FIELDS_ORDER_PATH = os.path.join(BASE, "rules", "field_order.yaml")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"

os.makedirs(EXPORT_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

with open(DECODE_PATH, "r", encoding="utf-8") as f:
    decode_maps = json.load(f)
with open(FIELDS_ORDER_PATH, "r", encoding="utf-8") as f:
    field_order = yaml.safe_load(f) or {}

loader = RdsLoader(RDS_DIR)
gap_analyzer = GapAnalyzer(min_similarity=0.7)

STATEMENT_MAP = {
    "income_statement": "IS", "balance_sheet": "BS", "cash_flow": "CF"
}
REPORT_TYPES = ["annual", "half", "q1", "q3"]

# ===== Collect all extracted files =====
all_files = []
for code_dir in sorted(os.listdir(EXTRACTED_DIR)):
    path = os.path.join(EXTRACTED_DIR, code_dir)
    if not os.path.isdir(path):
        continue
    for fname in sorted(os.listdir(path)):
        if not fname.endswith(".json"):
            continue
        all_files.append((code_dir, os.path.join(path, fname)))

print(f"Found {len(all_files)} extracted JSON files")

# ===== Process each file =====
tidy_rows = []
extracted_tidy_rows = []
all_comparisons = []
gap_summaries = []

for idx, (code, fpath) in enumerate(all_files):
    # Parse filename: 600519_2020_income_statement.json
    basename = os.path.basename(fpath)
    parts = basename.replace(".json", "").split("_")
    if len(parts) < 3:
        continue
    code = parts[0]
    year = int(parts[1]) if parts[1].isdigit() else 0
    st = "_".join(parts[2:])  # income_statement or balance_sheet or cash_flow
    if st not in STATEMENT_MAP:
        continue

    # Load extracted data
    with open(fpath, "r", encoding="utf-8") as f:
        extracted = json.load(f)
    ext_items = extracted.get("data", {}).get("data", {})
    if not ext_items:
        ext_items = extracted.get("data", {})

    # Load RDS ground truth
    rds_items = loader.load_stock_data(code, year, st)
    if not rds_items or len(rds_items) < 2:
        continue

    # Load aliases
    aliases = get_aliases(st, "annual")
    dm = decode_maps.get(st, {})

    # Compare
    comp = compare_stock(rds_items, ext_items, aliases,
                         stock_code=code, year=year,
                         statement_type=st, decode_map=dm)
    all_comparisons.append(comp)

    # Get display_order
    order_map = field_order.get(st, {})

    # Build Tidy rows from RDS (ground truth)
    reverse_decode = dm.get(st, {}) if dm else {}
    for item in comp.matched:
        code_for_item = item.ground_truth_code
        name_for_item = item.ground_truth_name
        value_for_item = item.ground_truth_value
        order = order_map.get(code_for_item, -1)

        tidy_rows.append({
            "stock_code": code,
            "report_year": year,
            "report_type": "annual",  # Default - can be refined
            "statement_type": st,
            "item_code": code_for_item,
            "item_name": name_for_item,
            "value": value_for_item,
            "display_order": order,
            "source": "rds",
            "match_type": item.match_type,
        })

    # Build Tidy rows from extracted (with code mapping where available)
    for name, val in ext_items.items():
        from astock_fundamentals.ground_truth.comparator import normalize_name
        nm = normalize_name(name)
        # Try to find the matching RDS code for this extracted name
        matched_code = None
        for item in comp.matched:
            if item.extracted_name and normalize_name(item.extracted_name) == nm:
                matched_code = item.ground_truth_code
                break
        order = order_map.get(matched_code, -1)

        extracted_tidy_rows.append({
            "stock_code": code,
            "report_year": year,
            "report_type": "annual",
            "statement_type": st,
            "item_code": matched_code,
            "item_name": name,
            "value": val,
            "display_order": order if matched_code else -1,
            "source": "pdf_extraction",
        })

    # Run Gap Analysis
    gap = GapSummary(
        stock_code=code,
        year=year,
        statement_type=st,
        missing_count=len(comp.missing),
        unmatched_count=len(comp.unmatched),
    )
    missing_set = {item.ground_truth_name for item in comp.missing}
    unmatched_set = {item.extracted_name for item in comp.unmatched}
    for rds_name in missing_set:
        rds_val = rds_items.get(rds_name)
        if rds_val is None or abs(rds_val) < 1:
            continue
        for ext_name in unmatched_set:
            ext_val = ext_items.get(ext_name)
            if ext_val is None or abs(ext_val) < 1:
                continue
            from astock_fundamentals.ground_truth.comparator import _compare_values
            err = _compare_values(rds_val, ext_val)
            if err is not None and err < 0.01:
                gap.value_match_suggestions.append((rds_name, ext_name, rds_val))

    gap_summaries.append(gap)

    if idx % 50 == 0:
        print(f"  processed {idx+1}/{len(all_files)} files...", flush=True)

# ===== Save Tidy Data =====
if tidy_rows:
    df_tidy = pd.DataFrame(tidy_rows)
    tidy_path = os.path.join(EXPORT_DIR, "tidy_data.csv")
    df_tidy.to_csv(tidy_path, index=False, encoding="utf-8-sig")
    print(f"\nTidy Data (RDS): {len(df_tidy)} rows → {tidy_path}")

if extracted_tidy_rows:
    df_ext = pd.DataFrame(extracted_tidy_rows)
    ext_path = os.path.join(EXPORT_DIR, "tidy_data_extracted.csv")
    df_ext.to_csv(ext_path, index=False, encoding="utf-8-sig")
    print(f"Tidy Data (extracted): {len(df_ext)} rows → {ext_path}")

# ===== Generate Gap Report =====
total_missing = sum(g.missing_count for g in gap_summaries)
total_unmatched = sum(g.unmatched_count for g in gap_summaries)
total_suggestions = sum(len(g.value_match_suggestions) for g in gap_summaries)

# Aggregate value suggestions by frequency
sugg_counts = defaultdict(list)
for g in gap_summaries:
    for rds_name, ext_name, val in g.value_match_suggestions:
        sugg_counts[(g.statement_type, rds_name, ext_name)].append(
            f"{g.stock_code}/{g.year}"
        )

sugg_rows = ""
for (st, rds_name, ext_name), evidence in sorted(sugg_counts.items(),
                                                    key=lambda x: -len(x[1])):
    if len(evidence) >= 2:  # Only show seen in 2+ stocks
        sugg_rows += f"<tr><td>{STATEMENT_MAP.get(st, st)}</td><td>{rds_name}</td><td>{ext_name}</td><td>{len(evidence)}</td><td>{'; '.join(evidence[:5])}</td></tr>"

# Summary by stock
stock_summary = defaultdict(lambda: {"tests": 0, "matched": 0, "missing": 0, "unmatched": 0})
for comp in all_comparisons:
    code = comp.stock_code
    s = comp.summary()
    stock_summary[code]["tests"] += 1
    stock_summary[code]["matched"] += s["matched"]
    stock_summary[code]["missing"] += s["missing"]
    stock_summary[code]["unmatched"] += s["unmatched"]

stock_rows = ""
for code, ss in sorted(stock_summary.items()):
    total_gt = ss["matched"] + ss["missing"]
    cov = f"{ss['matched']/total_gt*100:.1f}%" if total_gt else "-"
    stock_rows += f"<tr><td>{code}</td><td>{ss['tests']}</td><td>{ss['matched']}</td><td>{ss['missing']}</td><td>{ss['unmatched']}</td><td>{cov}</td></tr>"

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<title>Tidy Data 管线 - 差异分析报告</title>
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;margin:30px;background:#f5f5f5;font-size:13px}}
h1,h2{{color:#1a237e}}
.summary{{display:flex;gap:16px;margin:20px 0;flex-wrap:wrap}}
.card{{background:white;border-radius:8px;padding:16px 24px;box-shadow:0 1px 4px rgba(0,0,0,0.08);flex:1;text-align:center;min-width:150px}}
.card .big{{font-size:28px;font-weight:bold;color:#1a237e}}
.card .lbl{{font-size:12px;color:#666;margin-top:4px}}
table{{border-collapse:collapse;width:100%;background:white;border-radius:6px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.07);margin:15px 0}}
th{{background:#1a237e;color:white;padding:7px 10px;text-align:left;font-size:12px}}
td{{padding:6px 10px;border-bottom:1px solid #eee}}
tr:hover{{background:#e8eaf6}}
.good{{color:#2e7d32;font-weight:bold}}
.warn{{color:#e65100}}
.footer{{background:#e8eaf6;padding:10px 16px;border-radius:8px;margin-top:25px;font-size:12px}}
</style></head><body>
<h1>Tidy Data 管线 — 差异分析报告</h1>

<div class="summary">
<div class="card"><div class="big">{len(all_comparisons)}</div><div class="lbl">对比测试</div></div>
<div class="card"><div class="big">{len(stock_summary)}</div><div class="lbl">股票数</div></div>
<div class="card"><div class="big"><span class="good">{sum(s['matched'] for s in stock_summary.values())}</span></div><div class="lbl">匹配科目</div></div>
<div class="card"><div class="big"><span class="warn">{total_missing}</span></div><div class="lbl">缺失科目</div></div>
<div class="card"><div class="big">{total_suggestions}</div><div class="lbl">值匹配建议</div></div>
</div>

<h2>按股票汇总</h2>
<table><tr><th>代码</th><th>测试</th><th>匹配</th><th>缺失</th><th>多余</th><th>覆盖率</th></tr>{stock_rows}</table>

<h2>候选别名映射（值相同但名不同，2+ 股票）</h2>
<table><tr><th>报表</th><th>RDS 名称</th><th>提取名称</th><th>出现次数</th><th>证据</th></tr>
{sugg_rows if sugg_rows else '<tr><td colspan="5" style="text-align:center;color:#999">无高频候选映射</td></tr>'}
</table>

<div class="footer">
生成: {datetime.now().isoformat()[:19]}<br>
Tidy Data 输出: {os.path.join(EXPORT_DIR, 'tidy_data.csv')} | {os.path.join(EXPORT_DIR, 'tidy_data_extracted.csv')}<br>
规则: rules/field_order.yaml (display_order) | rules/value_mapping_rules.yaml (别名映射)
</div>
</body></html>'''

gap_html = os.path.join(REPORT_DIR, "tidy_gaps.html")
with open(gap_html, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Gap report: {gap_html}")

# ===== Summary =====
total_gt_items = sum(comp.summary()['gt_items'] for comp in all_comparisons)
total_matched = sum(comp.summary()['matched'] for comp in all_comparisons)
print(f"\n{'='*60}")
print(f"Tidy Data Pipeline Complete")
print(f"  Stocks: {len(stock_summary)}")
print(f"  Comparisons: {len(all_comparisons)}")
print(f"  Coverage: {total_matched}/{total_gt_items} = {total_matched/total_gt_items*100:.1f}%")
print(f"  Display order: from rules/field_order.yaml ({sum(len(v) for v in field_order.values())} codes)")
print(f"  Gap suggestions: {total_suggestions} value-matched pairs")
print(f"{'='*60}")
