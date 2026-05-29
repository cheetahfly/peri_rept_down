#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三源交叉对比: RDS vs AKShare(新浪) vs PDF提取

使用已有PDF提取数据 + 之前缓存的Sina数据（如有）+ RDS
"""
import sys, os, json, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.sources.pdf.parsers.pdf_parser import PdfParser
from astock_fundamentals.sources.pdf.extractors.income_statement import IncomeStatementExtractor
from astock_fundamentals.sources.pdf.extractors.balance_sheet import BalanceSheetExtractor
from astock_fundamentals.sources.pdf.extractors.cash_flow import CashFlowExtractor
from astock_fundamentals.ground_truth.comparator import compare_stock
from astock_fundamentals.core.extraction_config import get_aliases

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
PDF_DIR = os.path.join(BASE, "data", "pdfs")
OUTPUT = os.path.join(BASE, "data", "ground_truth_reports", "three_way_comparison.html")
SINA_CACHE = os.path.join(BASE, "data", "ground_truth_reports", "akshare_sina_cache.json")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"

with open(DECODE_PATH, "r", encoding="utf-8") as f:
    decode_maps = json.load(f)
loader = RdsLoader(RDS_DIR)

STOCKS = [
    ("000002", "万科A"), ("000858", "五粮液"), ("002415", "海康威视"),
    ("002475", "立讯精密"), ("300750", "宁德时代"),
    ("600519", "贵州茅台"), ("600887", "伊利股份"),
]
YEAR = 2020

# Use extracted data if already saved
EXTRACTED_DIR = os.path.join(BASE, "data", "extracted", "by_code", "600519")

STATEMENTS = [
    ("balance_sheet", "BS", BalanceSheetExtractor),
    ("income_statement", "IS", IncomeStatementExtractor),
    ("cash_flow", "CF", CashFlowExtractor),
]

# ===== Load previously extracted data (from earlier sessions) =====
pdf_cache = {}
for code, name in STOCKS:
    extracted_path = os.path.join(BASE, "data", "extracted", "by_code", code)
    pdf_cache[code] = {}
    for st, st_label, _ in STATEMENTS:
        fname = os.path.join(extracted_path, f"{code}_{YEAR}_{st}.json")
        if os.path.exists(fname):
            with open(fname, "r", encoding="utf-8") as f:
                data = json.load(f)
            pdf_cache[code][st] = data.get("data", {}).get("data", {})
            if not pdf_cache[code][st]:
                pdf_cache[code][st] = data.get("data", {})
        else:
            pdf_cache[code][st] = {}

# ===== Try loading pre-cached Sina data =====
sina_cache = {}
if os.path.exists(SINA_CACHE):
    with open(SINA_CACHE, "r", encoding="utf-8") as f:
        sina_cache = json.load(f)
    print(f"Loaded Sina cache: {len(sina_cache)} items")

# ===== Extract PDF data for stocks that don't have extracted JSON =====
print("Checking PDF extraction status...")
for code, name in STOCKS:
    has_any = any(pdf_cache[code].get(st) for st, _, _ in STATEMENTS)
    print(f"  {code} {name}: {'EXTRACTED' if has_any else 'NEED EXTRACT'}")

# Do extraction for any that need it
for code, name in STOCKS:
    for st, st_label, ExtractorCls in STATEMENTS:
        if pdf_cache[code].get(st):
            continue
        pdf_path = os.path.join(PDF_DIR, code, f"{code}_{YEAR}_annual.pdf")
        if not os.path.exists(pdf_path):
            continue
        try:
            with PdfParser(pdf_path) as parser:
                ext = ExtractorCls(parser)
                result = ext.extract()
                pdf_cache[code][st] = result.get("data", {})
                print(f"  Extracted {code} {st_label}: {len(pdf_cache[code][st])} items")
        except Exception as e:
            print(f"  FAILED {code} {st_label}: {e}")

# ===== Run comparisons =====
results = []
for code, name in STOCKS:
    pdf_items_any = any(pdf_cache[code].get(st) for st, _, _ in STATEMENTS)
    if not pdf_items_any:
        continue
    for st, st_label, _ in STATEMENTS:
        aliases = get_aliases(st, "annual")
        dm = decode_maps.get(st, {})

        try:
            rds = loader.load_stock_data(code, YEAR, st)
        except:
            rds = {}
        if not rds:
            continue

        pdf_items = pdf_cache[code].get(st, {})
        sina_items = sina_cache.get(f"{code}_{YEAR}_{st}", {})

        # RDS vs PDF
        comp_rp = compare_stock(rds, pdf_items, aliases, stock_code=code, year=YEAR, statement_type=st, decode_map=dm)
        srp = comp_rp.summary()

        # RDS vs Sina (if available)
        srs = {"matched": 0, "gt_items": 0, "coverage": 0, "value_accuracy": 0}
        if sina_items:
            comp_rs = compare_stock(rds, sina_items, aliases, stock_code=code, year=YEAR, statement_type=st, decode_map=dm)
            srs = comp_rs.summary()

        # Sina vs PDF (if both available)
        ssp = {"matched": 0, "gt_items": 0, "coverage": 0, "value_accuracy": 0}
        if sina_items and pdf_items:
            comp_sp = compare_stock(sina_items, pdf_items, aliases, stock_code=code, year=YEAR, statement_type=st, decode_map=dm)
            ssp = comp_sp.summary()

        results.append({
            "code": code, "name": name, "st": st_label,
            "rds_n": srp['gt_items'],
            "rp": srp, "rs": srs, "sp": ssp,
            "has_sina": bool(sina_items),
        })

# ===== HTML =====
detail_rows = ""
for r in results:
    rp, rs, sp = r['rp'], r['rs'], r['sp']
    detail_rows += f"""<tr>
<td>{r['code']}<br>{r['name']}</td><td>{r['st']}</td><td>{r['rds_n']}</td>
<td>{rs['matched']}/{rs['gt_items']}</td><td>{rs['coverage']*100:.0f}%</td><td>{rs['value_accuracy']*100:.0f}%</td>
<td>{rp['matched']}/{rp['gt_items']}</td><td>{rp['coverage']*100:.0f}%</td><td>{rp['value_accuracy']*100:.0f}%</td>
<td>{sp['matched']}/{sp['gt_items']}</td><td>{sp['coverage']*100:.0f}%</td>
<td>{'Y' if r['has_sina'] else '-'}</td>
</tr>"""

# Aggregate
aggs = {}
for lbl, key in [("RDS→Sina", "rs"), ("RDS→PDF", "rp"), ("Sina→PDF", "sp")]:
    items = [r for r in results if r[key]['gt_items'] > 0 and (key != "rs" or r['has_sina']) and (key != "sp" or (r['has_sina'] and r['rp']['gt_items'] > 0))]
    total = sum(r[key]['gt_items'] for r in items) or 1
    matched = sum(r[key]['matched'] for r in items)
    acc = sum(r[key]['value_accuracy'] * r[key]['gt_items'] for r in items) / total
    aggs[lbl] = (matched, total, matched/total*100, acc*100)

agg_rows = ""
for lbl, (m, t, cov, acc) in aggs.items():
    agg_rows += f"<tr><td><b>{lbl}</b></td><td>{m}/{t}</td><td>{cov:.1f}%</td><td>{acc:.1f}%</td></tr>"

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<title>三源交叉可靠性对比</title>
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;margin:30px;background:#f5f5f5;font-size:13px}}
h1,h2{{color:#1a237e}}
.summary{{display:flex;gap:16px;margin:20px 0}}
.card{{background:white;border-radius:8px;padding:16px 24px;box-shadow:0 1px 4px rgba(0,0,0,0.08);flex:1;text-align:center}}
.card .big{{font-size:28px;font-weight:bold}}
.card .lbl{{font-size:12px;color:#666;margin-top:4px}}
table{{border-collapse:collapse;width:100%;background:white;border-radius:6px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.07);margin:15px 0}}
th{{background:#1a237e;color:white;padding:7px 10px;text-align:left;font-size:12px}}
td{{padding:6px 10px;border-bottom:1px solid #eee;font-size:12px}}
tr:hover{{background:#e8eaf6}}
.num{{text-align:right}}
.footer{{background:#e8eaf6;padding:10px 16px;border-radius:8px;margin-top:25px;font-size:12px}}
.green{{color:#2e7d32;font-weight:bold}}
.amber{{color:#e65100}}
.na{{color:#999}}
</style>
</head><body>
<h1>三源交叉可靠性对比: RDS vs AKShare(新浪) vs PDF提取</h1>
<p>基准年份: 2020 | PDF源: 巨潮资讯网 | 新浪源: AKShare</p>

<div class="summary">
<div class="card"><div class="big" style="color:#1a237e">{sum(1 for r in set((r['code'],r['name']) for r in results))}</div><div class="lbl">股票(有PDF)</div></div>
<div class="card"><div class="big" style="color:#1565c0">{len(results)}</div><div class="lbl">对比测试</div></div>
</div>

<h2>总体可靠性矩阵</h2>
<table><tr><th>对比</th><th>匹配</th><th>覆盖率</th><th>值准确率</th></tr>{agg_rows}</table>

<p style="font-size:12px;color:#666">* RDS→Sina 仅含前期已成功获取新浪数据的部分。新浪API有请求频率限制，近期请求全部被限流。</p>

<h2>逐项明细</h2>
<table>
<tr><th>股票</th><th>报表</th><th>RDS</th>
<th colspan="3">RDS→Sina</th><th colspan="3">RDS→PDF</th><th colspan="2">Sina→PDF</th><th>Sina</th></tr>
<tr><th></th><th></th><th>科目</th>
<th>匹配</th><th>覆盖率</th><th>值准确率</th><th>匹配</th><th>覆盖率</th><th>值准确率</th><th>匹配</th><th>覆盖率</th><th>有</th></tr>
{detail_rows}
</table>

<div class="footer">
生成: {datetime.now().isoformat()[:19]}<br>
RDS: cninfo数据备份 | AKShare: v1.18.47 (新浪财经) | PDF: 巨潮资讯网公告
</div>
</body></html>'''

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"报告: {OUTPUT}")
print(f"股票: {len(set(r['code'] for r in results))}, 测试: {len(results)}")
for lbl, (m, t, cov, acc) in aggs.items():
    print(f"  {lbl}: {m}/{t} = {cov:.1f}%, acc={acc:.1f}%")
