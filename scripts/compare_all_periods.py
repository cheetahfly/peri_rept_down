#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多期对比: 新浪 vs RDS (2020-2022 × 全部报告期)

读取 data/akshare_bulk/ 中CSV/JSON格式的缓存数据，
与RDS进行逐期对比，生成覆盖率报告。
"""
import sys, os, json, warnings, glob
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
from datetime import datetime
from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.ground_truth.comparator import compare_stock, _compare_values, normalize_name
from astock_fundamentals.core.extraction_config import get_aliases

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE, "..", "data", "akshare_bulk")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "..", "data", "decode_mappings_by_type.json")
OUTPUT_HTML = os.path.join(BASE, "..", "data", "ground_truth_reports", "full_period_comparison.html")

with open(DECODE_PATH, "r", encoding="utf-8") as f:
    decode_maps = json.load(f)
loader = RdsLoader(RDS_DIR)

PERIOD_MAP = {"0331": "q1", "0630": "half", "0930": "q3", "1231": "annual"}
STATEMENT_MAP = {"balance_sheet": "BS", "income_statement": "IS", "cash_flow": "CF"}

# Load NEW format JSON files (multi-period: {period: {item: value}})
# or FALLBACK to OLD format (single period dict)
all_results = []
stocks_processed = set()

for fpath in sorted(glob.glob(os.path.join(CACHE_DIR, "*_*.json"))):
    fname = os.path.basename(fpath).replace(".json", "")
    if "_" not in fname or any(x in fname for x in ["stock_list", "download"]):
        continue
    code, st = fname.split("_", 1)
    if st not in STATEMENT_MAP:
        continue

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Detect format: multi-period dict (keys are date strings) or single-period dict
    keys = list(data.keys())[:5]
    is_multi = any(len(k) == 8 and k.isdigit() for k in keys) if keys else False

    if is_multi:
        # NEW format: { "20201231": {"货币资金": 36091090060.9, ...}, ... }
        for period_str, items in data.items():
            if len(period_str) != 8:
                continue
            year = period_str[:4]
            mmdd = period_str[4:]
            rt = PERIOD_MAP.get(mmdd)
            if not rt or year not in ("2020", "2021", "2022"):
                continue
            try:
                rds = loader.load_stock_data(code, int(year), st)
            except:
                continue
            if not rds:
                continue

            aliases = get_aliases(st, "annual")
            dm = decode_maps.get(st, {})
            comp = compare_stock(rds, items, aliases, stock_code=code, year=int(year), statement_type=st, decode_map=dm)
            s = comp.summary()
            all_results.append({**s, "code": code, "st": st, "period": period_str, "rt": rt})
            stocks_processed.add(code)
    else:
        # OLD format: single period dict (2020 annual fallback)
        try:
            rds = loader.load_stock_data(code, 2020, st)
        except:
            continue
        if not rds:
            continue
        aliases = get_aliases(st, "annual")
        dm = decode_maps.get(st, {})
        comp = compare_stock(rds, data, aliases, stock_code=code, year=2020, statement_type=st, decode_map=dm)
        s = comp.summary()
        all_results.append({**s, "code": code, "st": st, "period": "20201231", "rt": "annual"})
        stocks_processed.add(code)

# Generate HTML report
total_tests = len(all_results)
total_gt = sum(r['gt_items'] for r in all_results)
total_m = sum(r['matched'] for r in all_results)

# Aggregate by year and report type
agg = defaultdict(lambda: {"tests": 0, "gt": 0, "m": 0, "acc_sum": 0.0})
for r in all_results:
    key = f"{r['year']}_{r['rt']}"
    agg[key]["tests"] += 1
    agg[key]["gt"] += r['gt_items']
    agg[key]["m"] += r['matched']
    agg[key]["acc_sum"] += r['value_accuracy'] * r['gt_items']

agg_rows = ""
for key in sorted(agg):
    a = agg[key]
    cov = f"{a['m']/a['gt']*100:.1f}%" if a['gt'] else "-"
    acc = f"{a['acc_sum']/a['gt']*100:.1f}%" if a['gt'] else "-"
    agg_rows += f"<tr><td>{key}</td><td>{a['tests']}</td><td>{a['gt']}</td><td>{a['m']}</td><td>{cov}</td><td>{acc}</td></tr>"

# By stock
stk = defaultdict(lambda: {"tests": 0, "gt": 0, "m": 0})
for r in all_results:
    stk[r['code']]["tests"] += 1
    stk[r['code']]["gt"] += r['gt_items']
    stk[r['code']]["m"] += r['matched']

stk_rows = ""
for code in sorted(stk):
    s = stk[code]
    stk_rows += f"<tr><td>{code}</td><td>{s['tests']}</td><td>{s['gt']}</td><td>{s['m']}</td><td>{s['m']/s['gt']*100:.1f}%</td></tr>"

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<title>多期覆盖报告: 新浪 vs RDS</title>
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
.footer{{background:#e8eaf6;padding:10px 16px;border-radius:8px;margin-top:25px;font-size:12px}}
</style></head><body>
<h1>多期覆盖报告: AKShare(新浪) vs RDS</h1>
<p>报告期: 2020-2022 | 数据源: 新浪财经(缓存) + RDS(cninfo)</p>

<div class="summary">
<div class="card"><div class="big">{total_m}/{total_gt}</div><div class="lbl">总匹配 ({total_m/total_gt*100:.1f}%)</div></div>
<div class="card"><div class="big">{len(stocks_processed)}</div><div class="lbl">股票数</div></div>
<div class="card"><div class="big">{total_tests}</div><div class="lbl">对比测试</div></div>
</div>

<h2>按年份×报告期</h2>
<table><tr><th>年_期</th><th>测试</th><th>RDS科目</th><th>匹配</th><th>覆盖率</th><th>值准确率</th></tr>{agg_rows}</table>

<h2>按股票</h2>
<table><tr><th>代码</th><th>测试数</th><th>RDS科目</th><th>匹配</th><th>覆盖率</th></tr>{stk_rows}</table>

<h2>数据状态说明</h2>
<div style="background:#fff8e1;padding:12px 16px;border-radius:8px">
<p><b>当前缓存:</b> {len(stocks_processed)} 只股票 × {STATEMENT_MAP.values()} × 单期(2020年报)</p>
<p><b>多期数据:</b> 新浪API当前不可用(请求被限流)。升级后的下载脚本bulk_sina_download.py将保存RAW格式(全部报告期)，下次运行后即可生成完整多期报告。</p>
<p><b>下次运行方案:</b> python scripts/bulk_sina_download.py → python scripts/compare_all_periods.py</p>
</div>
<div class="footer">生成: {datetime.now().isoformat()[:19]}</div>
</body></html>'''

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Report: {OUTPUT_HTML}")
print(f"Stocks: {len(stocks_processed)}, Tests: {total_tests}, Coverage: {total_m}/{total_gt} = {total_m/total_gt*100:.1f}%")
