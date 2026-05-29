#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
600519 2020: AKShare(新浪) vs RDS 数据对比
"""
import sys, os, json, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.sources.api.akshare_provider import AKShareProvider
from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.ground_truth.comparator import compare_stock
from astock_fundamentals.core.extraction_config import get_aliases

stock_code = "600519"
year = 2020
report_type = "annual"

# ===== 1. 下载新浪数据 =====
provider = AKShareProvider()
print("Downloading 600519 2020 from Sina Finance via AKShare...")
sina_data = {}
for st, label in [("balance_sheet", "资产负债表"), ("income_statement", "利润表"), ("cash_flow", "现金流量表")]:
    data = provider._get_data_sina(stock_code, year, st, report_type)
    sina_data[st] = data or {}
    print(f"  {label}: {len(sina_data[st])} items")

# ===== 2. 加载 RDS 数据 =====
loader = RdsLoader("D:/Research/Quant/SETL/cninfo/data_backup")
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "decode_mappings_by_type.json"), "r", encoding="utf-8") as f:
    decode_maps = json.load(f)

print("\nLoading RDS data...")
rds_data = {}
for st in ["balance_sheet", "income_statement", "cash_flow"]:
    rds_data[st] = loader.load_stock_data(stock_code, year, st)
    print(f"  {st}: {len(rds_data[st])} items")

# ===== 3. 对比 =====
print("\n=== Comparison: AKShare(Sina) vs RDS ===")
all_diffs = []
all_missing = []

for st, label in [("balance_sheet", "资产负债表"), ("income_statement", "利润表"), ("cash_flow", "现金流量表")]:
    aliases = get_aliases(st, "annual")
    dm = decode_maps.get(st, {})
    comp = compare_stock(rds_data[st], sina_data[st], aliases,
                         stock_code=stock_code, year=year,
                         statement_type=st, decode_map=dm)
    s = comp.summary()
    print(f"\n{label}:")
    print(f"  Matched: {s['matched']}/{s['gt_items']} ({s['coverage']*100:.1f}%)")
    print(f"  Value accuracy: {s['value_accuracy']*100:.1f}%")
    print(f"  Missing: {s['missing']}, Unmatched: {s['unmatched']}")

    for item in comp.matched:
        if item.value_error_pct is not None and item.value_error_pct >= 1.0:
            all_diffs.append((label, st, item))
    for item in comp.missing:
        all_missing.append((label, st, item))

# ===== 4. 生成 HTML =====
missing_rows = ""
for label, st, item in all_missing:
    code = item.ground_truth_code or "-"
    name = item.ground_truth_name
    val = item.ground_truth_value
    missing_rows += f"<tr><td>{label}</td><td class='code'>{code}</td><td>{name}</td><td class='num'>{val:,.2f}</td><td class='badge missing'>缺失</td></tr>\n"

diff_rows = ""
for label, st, item in all_diffs:
    code = item.ground_truth_code or "-"
    name = item.ground_truth_name
    gt_val = item.ground_truth_value
    ext_val = item.extracted_value
    err = item.value_error_pct
    diff_rows += f"<tr><td>{label}</td><td class='code'>{code}</td><td>{name}</td><td class='num'>{gt_val:,.2f}</td><td class='num'>{ext_val:,.2f}</td><td class='num diff'>{err:.2f}%</td></tr>\n"

# 汇总表格
summary_rows = ""
for st, label in [("balance_sheet", "资产负债表"), ("income_statement", "利润表"), ("cash_flow", "现金流量表")]:
    s = compare_stock(rds_data[st], sina_data[st], get_aliases(st, "annual"),
                      stock_code=stock_code, year=year, statement_type=st,
                      decode_map=decode_maps.get(st, {})).summary()
    summary_rows += f"<tr><td>{label}</td><td>{s['gt_items']}</td><td>{s['matched']}</td><td>{s['missing']}</td><td>{s['coverage']*100:.1f}%</td><td>{s['value_accuracy']*100:.1f}%</td></tr>\n"

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><title>AKShare(新浪) vs RDS 对比 - 600519 2020</title>
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;margin:30px;background:#f5f5f5}}
h1{{font-size:22px;color:#1a237e}}
table{{border-collapse:collapse;width:100%;background:white;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08);margin:20px 0}}
th{{background:#1a237e;color:white;padding:10px 14px;text-align:left}}
td{{padding:10px 14px;border-bottom:1px solid #eee}}
tr:hover{{background:#e8eaf6}}
.code{{font-family:'Consolas',monospace;color:#1565c0}}
.num{{font-family:'Consolas',monospace;text-align:right}}
.diff{{color:#e65100;font-weight:bold}}
.badge{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:12px;font-weight:600}}
.badge.missing{{background:#ffebee;color:#c62828}}
.green{{color:#2e7d32;font-weight:bold}}
.stats{{display:flex;gap:16px;margin:20px 0}}
.card{{background:white;border-radius:8px;padding:16px 24px;box-shadow:0 1px 4px rgba(0,0,0,0.08);flex:1;text-align:center}}
.card .big{{font-size:30px;font-weight:bold}}
</style></head><body>
<h1>AKShare(新浪财经) vs RDS — 600519 2020 数据对比</h1>

<div class="stats">
<div class="card"><div class="big" style="color:#1a237e">新浪 → RDS</div><div style="font-size:13px;color:#666">使用 akshare.stock_financial_report_sina()</div></div>
</div>

<h2>汇总</h2>
<table><tr><th>报表</th><th>RDS科目数</th><th>匹配</th><th>缺失</th><th>覆盖率</th><th>值准确率</th></tr>
{summary_rows}
</table>

<h2>缺失的 RDS 科目 ({len(all_missing)})</h2>
<table><tr><th>报表</th><th>代码</th><th>科目</th><th>RDS值</th><th>状态</th></tr>
{missing_rows if missing_rows else "<tr><td colspan='5' style='color:#2e7d32;text-align:center'>无缺失 — 全部匹配</td></tr>"}
</table>

<h2>值差异 (>1%) ({len(all_diffs)})</h2>
<table><tr><th>报表</th><th>代码</th><th>科目</th><th>RDS值</th><th>新浪值</th><th>误差</th></tr>
{diff_rows if diff_rows else "<tr><td colspan='6' style='color:#2e7d32;text-align:center'>无差异 — 值完全一致</td></tr>"}
</table>

<div style="background:#e8eaf6;padding:12px 16px;border-radius:8px;margin-top:20px;font-size:13px">
下载时间: {__import__('datetime').datetime.now().isoformat()[:19]}<br>
数据来源: 新浪财经 (通过 AKShare v{__import__('importlib').import_module('akshare').__version__})
</div>
</body></html>'''

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "ground_truth_reports", "akshare_vs_rds.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"\nReport saved to: {out}")
