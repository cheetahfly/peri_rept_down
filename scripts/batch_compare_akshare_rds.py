#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量对比 AKShare(新浪) vs RDS — 简化版

对比范围: stock_universe 中的股票，RDS 中有的年报+半年报数据
"""
import sys, os, json, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from astock_fundamentals.sources.api.akshare_provider import AKShareProvider
from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.ground_truth.comparator import compare_stock
from astock_fundamentals.core.extraction_config import get_aliases

# ===== Config =====
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
OUTPUT = os.path.join(BASE, "data", "ground_truth_reports", "akshare_batch_comparison.html")

with open(DECODE_PATH, "r", encoding="utf-8") as f:
    decode_maps = json.load(f)

provider = AKShareProvider()
loader = RdsLoader(RDS_DIR)

# Test stocks (mix of industries, all in RDS)
STOCKS = [
    ("000001", "平安银行"), ("000002", "万科A"), ("000651", "格力电器"),
    ("000858", "五粮液"), ("002415", "海康威视"), ("600000", "浦发银行"),
    ("600036", "招商银行"), ("600519", "贵州茅台"), ("600585", "海螺水泥"),
    ("600887", "伊利股份"), ("601166", "兴业银行"), ("601318", "中国平安"),
    ("601398", "工商银行"), ("601628", "中国人寿"), ("601857", "中国石油"),
    ("601939", "建设银行"),
]
YEARS = [2020, 2021]
REPORT_TYPES = {"annual": "年报", "half": "半年报"}

results = []
print(f"批量对比开始: {datetime.now().isoformat()[:19]}")
print(f"{'股票':<12} {'报表':<6} {'年':<6} {'期':<8} {'匹配':<10} {'覆盖率':<10} {'值准确率':<10}")
print("-" * 70)

for code, name in STOCKS:
    for st, st_label in [("balance_sheet", "BS"), ("income_statement", "IS"), ("cash_flow", "CF")]:
        for year in YEARS:
            for rt, rt_label in REPORT_TYPES.items():
                # RDS
                try:
                    rds = loader.load_stock_data(code, year, st)
                except Exception:
                    continue
                if not rds:
                    continue

                # Sina
                try:
                    sina = provider._get_data_sina(code, year, st, rt)
                except Exception:
                    continue
                if not sina or len(sina) < 2:
                    continue

                # Compare
                aliases = get_aliases(st, "annual")
                dm = decode_maps.get(st, {})
                comp = compare_stock(rds, sina, aliases, stock_code=code,
                                     year=year, statement_type=st, decode_map=dm)
                s = comp.summary()

                results.append({**s, "stock_name": name, "st_label": st_label, "rt_label": rt_label})

                print(f"{code:<12} {st_label:<6} {year:<6} {rt_label:<8} "
                      f"{s['matched']}/{s['gt_items']:<6} {s['coverage']*100:>6.1f}%  "
                      f"{s['value_accuracy']*100:>6.1f}%")

# ===== Build summary HTML =====
total_gt = sum(r['gt_items'] for r in results)
total_matched = sum(r['matched'] for r in results)
overall = f"{total_matched}/{total_gt} ({total_matched/total_gt*100:.1f}%)" if total_gt else "-"

# Per-stock summary
code_summary = {}
for r in results:
    c = r['stock_code']
    if c not in code_summary:
        code_summary[c] = {"name": r['stock_name'], "gt": 0, "m": 0, "tests": 0, "acc_sum": 0.0, "acc_n": 0}
    code_summary[c]["gt"] += r['gt_items']
    code_summary[c]["m"] += r['matched']
    code_summary[c]["tests"] += 1
    if r['value_accuracy'] is not None:
        code_summary[c]["acc_sum"] += r['value_accuracy']
        code_summary[c]["acc_n"] += 1

def rep(rows):
    return "<table>" + "<tr>" + "".join(f"<th>{h}</th>" for h in rows[0]) + "</tr>" + \
           "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows[1:]) + "</table>"

st_rows = [["报表类型", "测试数", "RDS科目", "匹配", "缺失", "覆盖率", "值准确率"]]
for st, lbl in [("balance_sheet", "BS"), ("income_statement", "IS"), ("cash_flow", "CF")]:
    rs = [r for r in results if r['st_label'] == lbl]
    if not rs:
        continue
    gt = sum(r['gt_items'] for r in rs)
    m = sum(r['matched'] for r in rs)
    va = sum(r['value_accuracy'] * r['gt_items'] for r in rs) / gt if gt else 0
    st_rows.append([lbl, str(len(rs)), str(gt), str(m), str(gt - m),
                    f"{m/gt*100:.1f}%", f"{va*100:.1f}%"])

code_rows = [["股票", "测试数", "RDS科目", "匹配", "缺失", "覆盖率", "平均值准确率"]]
for c, sm in sorted(code_summary.items()):
    cov = f"{sm['m']/sm['gt']*100:.1f}%" if sm['gt'] else "-"
    acc = f"{sm['acc_sum']/sm['acc_n']*100:.1f}%" if sm['acc_n'] else "-"
    code_rows.append([f"{c} {sm['name']}", str(sm['tests']), str(sm['gt']),
                      str(sm['m']), str(sm['gt']-sm['m']), cov, acc])

detail_rows = [["股票", "报表", "年", "期", "RDS", "匹配", "缺失", "覆盖率", "值准确率"]]
for r in sorted(results, key=lambda x: (x['stock_code'], x['st_label'], x['year'])):
    detail_rows.append([
        f"{r['stock_code']} {r['stock_name']}", r['st_label'],
        str(r['year']), r['rt_label'],
        str(r['gt_items']), str(r['matched']), str(r['missing']),
        f"{r['coverage']*100:.1f}%",
        f"{r['value_accuracy']*100:.1f}%"])

html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>AKShare(新浪) vs RDS 批量对比</title>
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;margin:30px;background:#f5f5f5;font-size:13px}}
h1,h2{{color:#1a237e}}
table{{border-collapse:collapse;width:100%;background:white;border-radius:6px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.07);margin:15px 0}}
th{{background:#1a237e;color:white;padding:7px 10px;text-align:left}}
td{{padding:6px 10px;border-bottom:1px solid #eee}}
tr:hover{{background:#e8eaf6}}
.summary{{display:flex;gap:16px;margin:20px 0}}
.card{{background:white;border-radius:8px;padding:16px 24px;box-shadow:0 1px 4px rgba(0,0,0,0.08);flex:1;text-align:center}}
.card .big{{font-size:28px;font-weight:bold;color:#1a237e}}
.card .lbl{{font-size:12px;color:#666;margin-top:4px}}
.footer{{background:#e8eaf6;padding:10px 16px;border-radius:8px;margin-top:25px;font-size:12px}}
</style></head><body>
<h1>AKShare(新浪财经) vs RDS 批量对比</h1>
<div class="summary"><div class="card"><div class="big">{overall}</div><div class="lbl">总匹配</div></div>
<div class="card"><div class="big">{len(results)}</div><div class="lbl">测试数</div></div>
<div class="card"><div class="big">{len(code_summary)}</div><div class="lbl">股票数</div></div></div>
<h2>按报表类型</h2>{rep(st_rows)}
<h2>按股票</h2>{rep(code_rows)}
<h2>详细 ({len(detail_rows)-1} 条)</h2>{rep(detail_rows)}
<div class="footer">生成: {datetime.now().isoformat()[:19]} | 数据源: AKShare(新浪) vs RDS</div>
</body></html>'''

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"\n报告已保存: {OUTPUT}")
