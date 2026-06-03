#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三源一致性验证：PDF提取 vs 新浪API

对比有 PDF 提取和 Sina CSV 数据的股票。
输出：JSON (机器可读) + HTML (人眼可读)
"""
import sys, os, json, warnings
from typing import Dict
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime
from collections import defaultdict
from astock_fundamentals.ground_truth.comparator import compare_stock
from astock_fundamentals.core.extraction_config import get_aliases

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE, "..", "data", "akshare_bulk")
EXTRACTED_DIR = os.path.join(BASE, "..", "data", "extracted", "by_code")
DECODE_PATH = os.path.join(BASE, "..", "data", "decode_mappings_by_type.json")
OUTPUT_JSON = os.path.join(BASE, "..", "data", "exports_v2", "triple_source_comparison.json")
OUTPUT_HTML = os.path.join(BASE, "..", "data", "ground_truth_reports", "triple_source.html")

os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

with open(DECODE_PATH, "r", encoding="utf-8") as f:
    decode_maps = json.load(f)

STATEMENTS = ["balance_sheet", "income_statement", "cash_flow"]


def load_sina_annual(code: str, statement: str, year: int) -> Dict:
    """Load Sina CSV for specific year annual report."""
    csv_path = os.path.join(CACHE_DIR, f"{code}_{statement}.csv")
    if not os.path.exists(csv_path):
        return {}
    try:
        df = pd.read_csv(csv_path, dtype={0: str})
    except Exception:
        return {}
    row = df[df.iloc[:, 0] == f"{year}1231"]
    if row.empty:
        return {}
    items = {}
    for col in df.columns[1:]:
        try:
            val = row.iloc[0][col]
            if pd.notna(val) and str(val).replace(",", "").replace(".", "").replace("-", "").lstrip().isdigit():
                items[str(col)] = float(str(val).replace(",", ""))
        except:
            pass
    return items


def load_pdf_extracted(code: str, year: int, statement: str) -> Dict:
    """Load PDF extracted data."""
    fname = os.path.join(EXTRACTED_DIR, code, f"{code}_{year}_{statement}.json")
    if not os.path.exists(fname):
        return {}
    try:
        with open(fname, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("data", {}).get("data", {})
        if not items:
            items = data.get("data", {})
        return items
    except Exception:
        return {}


# ===== Collect stocks with both PDF and Sina data =====
pdf_stocks = set()
if os.path.isdir(EXTRACTED_DIR):
    for d in os.listdir(EXTRACTED_DIR):
        pdf_path = os.path.join(EXTRACTED_DIR, d)
        if os.path.isdir(pdf_path):
            # Check if has 2020 data
            for f in os.listdir(pdf_path):
                if "_2020_" in f and f.endswith(".json"):
                    pdf_stocks.add(d)
                    break

sina_stocks = set()
for fpath in os.listdir(CACHE_DIR):
    if fpath.endswith("_balance_sheet.csv"):
        sina_stocks.add(fpath.replace("_balance_sheet.csv", ""))

triple = sorted(pdf_stocks & sina_stocks)
print(f"PDF stocks (2020): {sorted(pdf_stocks)}")
print(f"Sina stocks: {len(sina_stocks)}")
print(f"Triple overlap (2020): {triple}")

# ===== Run comparison =====
all_results = []
for code in triple:
    for st in STATEMENTS:
        aliases = get_aliases(st, "annual")
        dm = decode_maps.get(st, {})

        pdf_items = load_pdf_extracted(code, 2020, st)
        sina_items = load_sina_annual(code, st, 2020)

        if not pdf_items or not sina_items:
            continue

        comp = compare_stock(pdf_items, sina_items, aliases,
                              stock_code=code, year=2020,
                              statement_type=st, decode_map=dm)
        s = comp.summary()
        results_row = {
            "stock": code, "year": 2020, "st": st, "source_pair": "pdf_vs_sina",
            **s,
            "missing_items": [item.ground_truth_name for item in comp.missing],
            "unmatched_items": [item.extracted_name for item in comp.unmatched],
        }
        all_results.append(results_row)
        print(f"  {code} {st}: {s['matched']}/{s['gt_items']} ({s['coverage']*100:.1f}%)")

# ===== Save JSON =====
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
print(f"\nJSON: {OUTPUT_JSON}")

# ===== Generate HTML =====
pair_summary = defaultdict(lambda: {"tests": 0, "gt": 0, "m": 0, "acc_sum": 0.0})
for r in all_results:
    pair_summary["pdf_vs_sina"]["tests"] += 1
    pair_summary["pdf_vs_sina"]["gt"] += r["gt_items"]
    pair_summary["pdf_vs_sina"]["m"] += r["matched"]
    pair_summary["pdf_vs_sina"]["acc_sum"] += r["value_accuracy"] * r["gt_items"]

a = pair_summary["pdf_vs_sina"]
cov = f"{a['m']/a['gt']*100:.1f}%" if a["gt"] else "-"
acc = f"{a['acc_sum']/a['gt']*100:.1f}%" if a["gt"] else "-"

# Per-stock breakdown
stock_rows = ""
for code in sorted(set(r["stock"] for r in all_results)):
    stock_res = [r for r in all_results if r["stock"] == code]
    st_rows = ""
    for r in stock_res:
        cov_val = f"{r['matched']}/{r['gt_items']} ({r['coverage']*100:.1f}%)"
        acc_val = f"{r['value_accuracy']*100:.1f}%"
        st_rows += f"<tr><td>{r['st']}</td><td>{r['matched']}</td><td>{r['gt_items']}</td><td>{cov_val}</td><td>{acc_val}</td></tr>"
    total_gt = sum(r["gt_items"] for r in stock_res)
    total_m = sum(r["matched"] for r in stock_res)
    stock_cov = f"{total_m/total_gt*100:.1f}%" if total_gt else "-"
    stock_rows += f"""<tr style="background:#f0f0f0;font-weight:bold">
<td>{code}</td><td>{len(stock_res)}</td><td>{total_m}</td><td>{total_gt}</td><td>{stock_cov}</td></tr>"""

total_gt = sum(r["gt_items"] for r in all_results)
total_m = sum(r["matched"] for r in all_results)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<title>三源一致性验证</title>
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;margin:30px;background:#f5f5f5;font-size:13px}}
h1,h2{{color:#1a237e}}
.summary{{display:flex;gap:16px;margin:20px 0;flex-wrap:wrap}}
.card{{background:white;border-radius:8px;padding:16px 24px;box-shadow:0 1px 4px rgba(0,0,0,0.08);flex:1;text-align:center;min-width:160px}}
.card .big{{font-size:28px;font-weight:bold;color:#1a237e}}
.card .lbl{{font-size:12px;color:#666;margin-top:4px}}
table{{border-collapse:collapse;width:100%;background:white;border-radius:6px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.07);margin:15px 0}}
th{{background:#1a237e;color:white;padding:7px 10px;text-align:left;font-size:12px}}
td{{padding:6px 10px;border-bottom:1px solid #eee;font-size:12px}}
tr:hover{{background:#e8eaf6}}
.good{{color:#2e7d32;font-weight:bold}}
.warn{{color:#e65100}}
.section{{background:white;border-radius:8px;padding:16px 24px;box-shadow:0 1px 4px rgba(0,0,0,0.08);margin:20px 0}}
.footer{{background:#e8eaf6;padding:10px 16px;border-radius:8px;margin-top:25px;font-size:12px}}
</style></head><body>
<h1>三源一致性验证</h1>
<p>数据源: PDF提取 vs AKShare(新浪财经) | 年份: 2020 | 对比范围: PDF+Sina重叠股票</p>

<div class="summary">
<div class="card"><div class="big">{total_m}/{total_gt}</div><div class="lbl">总匹配 ({cov})</div></div>
<div class="card"><div class="big">{len(triple)}</div><div class="lbl">三源重叠股票</div></div>
<div class="card"><div class="big">{len(all_results)}</div><div class="lbl">对比测试数</div></div>
<div class="card"><div class="big">{acc}</div><div class="lbl">值准确率</div></div>
</div>

<div class="section">
<h2>PDF vs Sina (2020)</h2>
<table><tr><th>代码</th><th>测试数</th><th>匹配</th><th>科目数</th><th>覆盖率</th></tr>
{stock_rows}
<tr style="background:#1a237e;color:white;font-weight:bold">
<td>总计</td><td>{a['tests']}</td><td>{a['m']}</td><td>{a['gt']}</td><td>{cov}</td></tr>
</table>
</div>

<div class="section">
<h2>说明</h2>
<ul>
<li><strong>覆盖率</strong>: 在 PDF 提取和 Sina 数据中，同名且值一致的科目数 / RDS 科目数</li>
<li><strong>值准确率</strong>: 已匹配科目中值误差 &lt; 1% 的比例</li>
<li>对比范围限于 PDF+Sina 双源重叠股票 (600519 等不在 Sina bulk 中)</li>
<li>RDS 数据暂未加载（pyreadr 加载超时），后续可补充三源交叉验证</li>
</ul>
</div>

<div class="footer">
生成: {datetime.now().isoformat()[:19]} | 三源验证: PDF提取 vs AKShare(新浪) | 报告期: 2020
</div>
</body></html>'''

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)
print(f"HTML: {OUTPUT_HTML}")

print(f"\n{'='*60}")
print(f"Triple-Source Verification: {total_m}/{total_gt} = {total_m/total_gt*100:.1f}%")
print(f"{'='*60}")
