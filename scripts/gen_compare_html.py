#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate Guosen vs Sina comparison HTML for 600519 2025."""

import json
import os
import sys
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, '.')
from astock_fundamentals.ground_truth.sina_loader import SinaLoader

# Load Guosen data
with open('data/guosen_600519_2025.json', 'r', encoding='utf-8') as f:
    guosen = json.load(f)

# Load Sina data
sina = SinaLoader('data/akshare_bulk')
sina_bs = sina.get_annual('600519', [2025], 'balance_sheet').iloc[0].to_dict()
sina_is = sina.get_annual('600519', [2025], 'income_statement').iloc[0].to_dict()
sina_cf = sina.get_annual('600519', [2025], 'cash_flow').iloc[0].to_dict()

# Guosen lookup
g_bs = {r['name']: r['value'] for r in guosen['BS']['rows']}
g_is = {r['name']: r['value'] for r in guosen['IS']['rows']}


def to_num(v):
    try:
        f = float(v)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


def fmt_exact(v):
    f = to_num(v)
    if f is None:
        return '—'
    if f == int(f):
        return f"{int(f):,}"
    return f"{f:,.4f}".rstrip('0').rstrip('.')


def build_match(g_dict, s_dict, name_mapping):
    """name_mapping: {canonical: (guosen_name, sina_name)}"""
    rows = []
    for canon, (g_name, s_name) in name_mapping.items():
        gv = g_dict.get(g_name)
        sv = s_dict.get(s_name)
        gf, sf = to_num(gv), to_num(sv)
        if gf is None and sf is None:
            continue
        diff_pct = None
        if gf and sf and gf != 0:
            diff_pct = abs(gf - sf) / abs(gf) * 100
        rows.append((canon, g_name, s_name, gv, sv, diff_pct))
    return rows


BS_MAP = {
    '总资产':       ('资产总计', '资产总计'),
    '流动资产合计': ('流动资产', '流动资产合计'),
    '非流动资产合计': ('非流动资产', '非流动资产合计'),
    '货币资金':     ('货币资金', '货币资金'),
    '应收账款':     ('应收账款', '应收账款'),
    '存货':         ('存货', '存货'),
    '固定资产':     ('固定资产', '固定资产'),
    '流动负债合计': ('流动负债', '流动负债合计'),
    '非流动负债合计': ('非流动负债', '非流动负债合计'),
    '负债合计':     ('负债合计', '负债合计'),
    '实收资本':     ('实收资本', '实收资本（或股本）'),
    '资本公积':     ('资本公积', '资本公积'),
    '盈余公积':     ('盈余公积', '盈余公积'),
    '未分配利润':   ('未分配利润', '未分配利润'),
    '归母权益':     ('所有者权益（或股东权益）合计', '归属于母公司股东权益合计'),
    '少数股东权益': ('少数股东权益', '少数股东权益'),
    '所有者权益合计': ('所有者权益（或股东权益）合计', '所有者权益合计'),
}

IS_MAP = {
    '营业总收入':   ('营业收入', '营业总收入'),
    '营业总成本':   ('营业支出', '营业总成本'),
    '营业利润':     ('营业利润', '营业利润'),
    '利润总额':     ('利润总额', '利润总额'),
    '所得税费用':   ('所得税费用', '所得税费用'),
    '净利润':       ('净利润', '净利润'),
    '归母净利润':   ('归属于母公司所有者的净利润', '归属于母公司股东的净利润'),
    '少数股东损益': ('少数股东损益', '少数股东损益'),
    '基本每股收益': ('基本每股收益', '基本每股收益'),
}

bs_rows = build_match(g_bs, sina_bs, BS_MAP)
is_rows = build_match(g_is, sina_is, IS_MAP)


def stats(rows):
    if not rows:
        return 0, 0, 0
    total = len(rows)
    match = sum(1 for r in rows if r[5] is not None and r[5] < 0.5)
    mid = sum(1 for r in rows if r[5] is not None and 0.5 <= r[5] < 5)
    low = total - match - mid
    return match, mid, low


bs_match, bs_mid, bs_low = stats(bs_rows)
is_match, is_mid, is_low = stats(is_rows)


def match_badge(diff_pct):
    if diff_pct is None:
        return '<span style="color:#7f8c8d">—</span>'
    if diff_pct < 0.5:
        return '<span class="match-high">&#x2713; ' + f'{diff_pct:.2f}%</span>'
    if diff_pct < 5:
        return '<span class="match-mid">&#x2248; ' + f'{diff_pct:.2f}%</span>'
    return '<span class="match-low">&#x2717; ' + f'{diff_pct:.2f}%</span>'


# Build HTML using triple-quoted string
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>国信 vs Sina - 600519 2025 年报对比</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #fafbfc; color: #2c3e50; padding: 24px; }
  .header { max-width: 1300px; margin: 0 auto 24px; padding: 24px; background: #fff;
            border: 1px solid #e1e4e8; border-radius: 8px; }
  h1 { font-size: 24px; color: #2c3e50; border-bottom: 2px solid #3498db;
       padding-bottom: 12px; margin-bottom: 12px; }
  .subtitle { color: #7f8c8d; font-size: 13px; margin-top: 6px; }
  .gen { color: #95a5a6; font-size: 11px; float: right; }
  .kpi-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 20px 0; }
  .kpi { background: #f0f7ff; border-left: 4px solid #3498db; padding: 14px 16px; border-radius: 4px; }
  .kpi-label { color: #7f8c8d; font-size: 12px; }
  .kpi-value { color: #2c3e50; font-size: 14px; font-weight: 700; margin-top: 4px;
                font-family: 'SF Mono', Monaco, monospace; word-break: break-all; }
  .kpi-delta { font-size: 11px; margin-top: 4px; }
  .card { background: #fff; border: 1px solid #e1e4e8; border-radius: 8px; padding: 20px; margin: 20px 0; }
  .card h2 { color: #2c3e50; font-size: 16px; border-bottom: 1px solid #e1e4e8;
            padding-bottom: 8px; margin-bottom: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: #f6f8fa; color: #2c3e50; font-weight: 600; padding: 8px 10px;
        text-align: left; border-bottom: 2px solid #e1e4e8; }
  td { padding: 6px 10px; border-bottom: 1px solid #eef0f2; }
  td.num { text-align: right; font-family: 'SF Mono', Monaco, monospace; }
  tr.match-high { background: #f0fdf4; }
  tr.match-mid  { background: #fef9c3; }
  tr.match-low  { background: #fee2e2; }
  .match-high { color: #16a34a; font-weight: 700; }
  .match-mid  { color: #b45309; font-weight: 700; }
  .match-low  { color: #dc2626; font-weight: 700; }
  .note { background: #fff7ed; border-left: 3px solid #f59e0b; padding: 10px 14px;
          margin: 12px 0; border-radius: 4px; font-size: 13px; color: #92400e; }
  .summary { background: #eef6ff; border: 1px solid #bfdbfe; border-radius: 8px;
              padding: 16px 20px; margin: 20px 0; }
  .summary h2 { color: #1e40af; font-size: 16px; margin-bottom: 10px; }
  .stat { display: inline-block; margin-right: 30px; }
  .stat-label { color: #64748b; font-size: 12px; }
  .stat-value { font-size: 22px; font-weight: 700; color: #1e40af; font-family: 'SF Mono', monospace; }
</style>
</head>
<body>
<div class="header">
  <h1>国信 (Guosen) vs Sina (AKShare) 数据对比</h1>
  <div class="subtitle">600519 贵州茅台 · 2025 年度报告 · 单位: 元（精确）</div>
  <div class="gen">生成于 GEN_TIME</div>
</div>
SUMMARY_BLOCK
KPI_BLOCK
CF_NOTE
BS_TABLE
IS_TABLE
CF_TABLE
APPENDIX
</body></html>
"""

# Build summary block
SUMMARY_BLOCK = f'''<div class="summary"><h2>📊 整体匹配概况</h2>
<span class="stat"><span class="stat-label">BS 完全匹配 (差异&lt;0.5%)</span><br><span class="stat-value">{bs_match}/{len(bs_rows)}</span></span>
<span class="stat"><span class="stat-label">IS 完全匹配</span><br><span class="stat-value">{is_match}/{len(is_rows)}</span></span>
<span class="stat"><span class="stat-label">BS 显著差异 (&gt;5%)</span><br><span class="stat-value" style="color:#dc2626">{bs_low}</span></span>
<span class="stat"><span class="stat-label">IS 显著差异</span><br><span class="stat-value" style="color:#dc2626">{is_low}</span></span>
</div>'''


def kpi_block(title, g_val, s_val, diff_pct):
    badge = match_badge(diff_pct)
    g_str = fmt_exact(g_val) if g_val is not None else '—'
    s_str = fmt_exact(s_val) if s_val is not None else '—'
    return f'''<div class="kpi">
      <div class="kpi-label">{title}</div>
      <div class="kpi-value">国信: {g_str} 元</div>
      <div class="kpi-value" style="font-size:13px;color:#7f8c8d">Sina: {s_str} 元</div>
      <div class="kpi-delta">差异: {badge}</div>
    </div>'''


kpi_items = [
    ('总资产', '资产总计', '资产总计'),
    ('营业收入', '营业总收入', '营业总收入'),
    ('净利润', '净利润', '净利润'),
]

kpi_html_parts = []
for title, g_key, s_key in kpi_items:
    gv = g_bs.get(g_key) or g_is.get(g_key)
    sv = sina_bs.get(s_key) or sina_is.get(s_key)
    gf, sf = to_num(gv), to_num(sv)
    diff = abs(gf - sf) / abs(gf) * 100 if gf and sf and gf != 0 else None
    kpi_html_parts.append(kpi_block(title, gv, sv, diff))

KPI_BLOCK = '<div class="kpi-row">' + ''.join(kpi_html_parts) + '</div>'

CF_NOTE = '<div class="note">⚠️ <b>现金流量表</b>: 国信 API 对 600519 返回空 (cashflow=[])。仅展示 Sina 侧数据。</div>'


def comp_table(title, rows):
    out = f'<div class="card"><h2>{title} ({len(rows)} 项)</h2><table>'
    out += '<thead><tr><th>科目</th><th>国信 (元)</th><th>Sina (元)</th><th>差异</th></tr></thead><tbody>'
    for canon, g_name, s_name, gv, sv, diff in rows:
        g_str = fmt_exact(gv)
        s_str = fmt_exact(sv)
        badge = match_badge(diff)
        diff_class = ('match-high' if diff is not None and diff < 0.5
                      else ('match-mid' if diff is not None and diff < 5 else 'match-low'))
        out += f'<tr class="{diff_class}">'
        out += f'<td><b>{canon}</b><br><span style="color:#95a5a6;font-size:11px">国信: {g_name}</span><br><span style="color:#95a5a6;font-size:11px">Sina: {s_name}</span></td>'
        out += f'<td class="num">{g_str}</td><td class="num">{s_str}</td><td>{badge}</td></tr>'
    out += '</tbody></table></div>'
    return out


BS_TABLE = comp_table('📋 资产负债表 (BS) 对比', bs_rows)
IS_TABLE = comp_table('📋 利润表 (IS) 对比', is_rows)

# CF: Sina only
cf_keywords = ['经营活动', '投资活动', '筹资活动', '现金及现金等价物净增加', '购建固定资产',
               '收到其他与', '支付其他与', '处置', '分配股利', '取得借款', '偿还债务',
               '净利润', '财务费用', '资产减值', '折旧', '摊销', '存货', '应收', '应付']
cf_rows_data = [(k, v) for k, v in sina_cf.items()
                 if any(m in k for m in cf_keywords)]

cf_html = '<div class="card"><h2>📋 现金流量表 (CF) - 仅 Sina 数据 (国信 CF 接口返回空)</h2><table>'
cf_html += '<thead><tr><th>科目 (Sina 字段名)</th><th class="num">金额 (元)</th></tr></thead><tbody>'
for k, v in cf_rows_data:
    cf_html += f'<tr><td>{k}</td><td class="num">{fmt_exact(v)}</td></tr>'
cf_html += '</tbody></table></div>'

CF_TABLE = cf_html

APPENDIX = '''<div class="card"><h2>📦 原始数据源</h2>
<ul style="line-height:1.8">
<li><code>data/guosen_600519_2025.json</code> - 国信 API 原始数据 (BS 40 / IS 31 / CF 0 项)</li>
<li><code>data/akshare_bulk/600519_*_statement.csv</code> - Sina AKShare 原始数据</li>
</ul></div>'''

html = HTML_TEMPLATE.replace('GEN_TIME', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
html = html.replace('SUMMARY_BLOCK', SUMMARY_BLOCK)
html = html.replace('KPI_BLOCK', KPI_BLOCK)
html = html.replace('CF_NOTE', CF_NOTE)
html = html.replace('BS_TABLE', BS_TABLE)
html = html.replace('IS_TABLE', IS_TABLE)
html = html.replace('CF_TABLE', CF_TABLE)
html = html.replace('APPENDIX', APPENDIX)

out = 'docs/temp_600519_compare.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Wrote {out} ({len(html)} bytes)')
print(f'\n匹配概况:')
print(f'  BS: {bs_match}/{len(bs_rows)} 完全匹配, {bs_mid} 接近, {bs_low} 差异>5%')
print(f'  IS: {is_match}/{len(is_rows)} 完全匹配, {is_mid} 接近, {is_low} 差异>5%')

abs_path = os.path.abspath(out)
print(f'\nURL: file:///{abs_path.replace(chr(92), chr(47))}')
