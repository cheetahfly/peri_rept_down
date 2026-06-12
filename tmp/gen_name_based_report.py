# -*- coding: utf-8 -*-
"""Generate comprehensive tushare vs RDS comparison report with name-based mapping"""
import json

with open('tmp/name_based_comparison.json', encoding='utf-8') as f:
    all_results = json.load(f)

stocks_meta = {
    '600519': '贵州茅台', '600887': '伊利股份', '000651': '格力电器',
    '688981': '中芯国际', '300750': '宁德时代', '600036': '招商银行',
}
boards = {
    '600519': '沪主板', '600887': '沪主板', '000651': '深主板',
    '688981': '科创板', '300750': '创业板', '600036': '沪主板(金融)',
}

color_css = {
    'exact': '#c8eac8', 'sub_yuan': '#f4e4b4', 'rounded': '#ffe0a3',
    'large_error': '#f5c2c2', 'no_match': '#e8e8e8',
}

# Build summary
summary_rows = []
total_all = {'exact': 0, 'sub_yuan': 0, 'rounded': 0, 'large_error': 0}

for code, r in all_results.items():
    name = stocks_meta[code]
    board = boards[code]
    c = r['counts']
    total = r['total']
    exact_rate = r['exact_rate']
    color = '#16a34a' if exact_rate >= 95 else '#d97706' if exact_rate >= 80 else '#dc2626'
    for k, v in c.items():
        if k in total_all:
            total_all[k] += v
    summary_rows.append(
        f'<tr><td><strong>{code}</strong></td><td>{name}</td><td>{board}</td>'
        f'<td class="num">{r["ts_count"]}</td><td class="num">{r["rds_count"]}</td>'
        f'<td class="num">{total}</td>'
        f'<td class="num" style="color:{color};font-weight:700">{exact_rate:.1f}%</td>'
        f'<td class="num">{c.get("exact",0)}</td>'
        f'<td class="num">{c.get("sub_yuan",0)}</td>'
        f'<td class="num">{c.get("rounded",0)}</td>'
        f'<td class="num">{c.get("large_error",0)}</td>'
        f'<td class="num">{len(r.get("unmatched_ts",[]))}</td>'
        f'<td class="num">{len(r.get("unmatched_rds",[]))}</td>'
        f'</tr>'
    )

total_matched = sum(total_all.values())
total_exact_rate = total_all['exact'] / total_matched * 100 if total_matched else 0

# Build per-stock details
stock_sections = []
for code in ['600519', '600887', '000651', '688981', '300750', '600036']:
    r = all_results.get(code, {})
    name = stocks_meta[code]
    board = boards[code]
    if r.get('total', 0) == 0:
        stock_sections.append(
            f'<div id="s{code}"></div><h2>{code} {name} ({board})</h2>'
            f'<p style="color:#999">无数据（金融股 comp_type 限制）</p>'
        )
        continue

    # Matched items table
    matched_rows = []
    for m in sorted(r['matched'], key=lambda x: (x['stmt'], x['rds_name'])):
        bg = color_css.get(m['class'], '#fff')
        ts_v = f"{m['ts_val']:,.2f}"
        rds_v = f"{m['rds_val']:,.2f}"
        diff = f"{m['diff']:,.2f}"
        rel = f"{m['rel']:.4f}%" if m['rel'] != 0 else "—"
        matched_rows.append(
            f'<tr style="background:{bg}">'
            f'<td>{m["rds_code"]}</td><td>{m["rds_name"]}</td><td class="num">{rds_v}</td>'
            f'<td>{m["ts_field"]}</td><td class="num">{ts_v}</td>'
            f'<td class="num">{diff}</td><td class="num">{rel}</td>'
            f'<td>{m["class"]}</td></tr>'
        )

    # Unmatched tushare fields
    ts_unmatched_rows = []
    for u in r.get('unmatched_ts', []):
        ts_unmatched_rows.append(
            f'<tr><td>{u["field"]}</td><td class="num">{u["value"]:,.2f}</td>'
            f'<td>{u.get("mapped_rds") or "无对应RDS字段"}</td></tr>'
        )

    # Unmatched RDS fields
    rds_unmatched_rows = []
    for u in r.get('unmatched_rds', []):
        rds_unmatched_rows.append(
            f'<tr><td>{u["code"]}</td><td>{u["name"]}</td><td class="num">{u["value"]:,.2f}</td></tr>'
        )

    c = r['counts']
    total = r['total']
    exact_rate = r['exact_rate']
    summary_line = ' · '.join(f'{k}={v}' for k, v in c.items() if v > 0)

    stock_sections.append(f'''
<div id="s{code}"></div>
<h2>{code} {name} ({board})</h2>
<div class="summary" style="background:#fff8db;border-left-color:#f0ad4e;">
<strong>name-based 匹配：</strong> {total} 项 · <strong>exact_rate：</strong> {exact_rate:.1f}%<br>
<strong>分布：</strong> {summary_line}<br>
<strong>tushare 字段总数：</strong> {r["ts_count"]} · <strong>RDS 字段总数：</strong> {r["rds_count"]} ·
<strong>tushare 未匹配：</strong> {len(r.get("unmatched_ts",[]))} ·
<strong>RDS 未匹配：</strong> {len(r.get("unmatched_rds",[]))}
</div>
<h3>匹配项（name-based）</h3>
<table>
<thead><tr><th>RDS 代码</th><th>RDS 项目</th><th>RDS 值</th><th>tushare 字段</th><th>tushare 值</th><th>差异(元)</th><th>相对误差</th><th>分类</th></tr></thead>
<tbody>{"".join(matched_rows)}</tbody>
</table>
{"<h3>tushare 未匹配字段 (" + str(len(ts_unmatched_rows)) + " 项)</h3><table><thead><tr><th>tushare 字段</th><th>值</th><th>映射目标</th></tr></thead><tbody>" + "".join(ts_unmatched_rows) + "</tbody></table>" if ts_unmatched_rows else ""}
{"<h3>RDS 未匹配字段 (" + str(len(rds_unmatched_rows)) + " 项)</h3><table><thead><tr><th>RDS 代码</th><th>RDS 项目</th><th>RDS 值</th></tr></thead><tbody>" + "".join(rds_unmatched_rows) + "</tbody></table>" if rds_unmatched_rows else ""}
''')

body_html = "\n".join(stock_sections)

html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Tushare vs RDS 综合对比报告（name-based mapping）</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"Microsoft YaHei",sans-serif;padding:20px;background:#f5f7fa;color:#1a202c}}
h1{{color:#1a1a2e;border-bottom:4px solid #8b5cf6;padding-bottom:12px;font-size:26px}}
h2{{color:#2d3748;border-left:4px solid #8b5cf6;padding-left:12px;margin-top:32px}}
h3{{color:#4a5568;margin-top:20px;font-size:16px}}
.summary{{padding:12px;border-left:4px solid #f0ad4e;margin:8px 0;background:#fff8db;border-radius:4px;font-size:13px}}
table{{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0;background:#fff;border-radius:4px;overflow:hidden}}
th{{background:#1a1a2e;color:#fff;padding:6px 10px;text-align:left;font-size:11px}}
td{{padding:5px 10px;border:1px solid #e1e4e8}}
.num{{text-align:right;font-family:Consolas,monospace;font-size:12px}}
.kpi{{display:inline-block;padding:10px 20px;margin:6px;background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08);text-align:center}}
.kpi-val{{font-size:28px;font-weight:700}}
.kpi-label{{font-size:11px;color:#718096}}
.toc{{background:#fff;padding:16px;border-radius:8px;margin:16px 0;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.toc a{{color:#8b5cf6;text-decoration:none}}
code{{background:#f1f5f9;padding:1px 4px;border-radius:3px;font-size:12px}}
</style></head><body>
<h1>📊 Tushare vs RDS 综合对比报告（name-based mapping）</h1>
<p style="color:#718096;margin:8px 0">6 只股票 × 2020 年报 × 3 表（BS/IS/CF）· 144 个 tushare→RDS 映射 · name-based 匹配</p>

<div style="margin:16px 0">
<div class="kpi"><div class="kpi-val" style="color:#16a34a">{total_exact_rate:.1f}%</div><div class="kpi-label">总 exact_rate</div></div>
<div class="kpi"><div class="kpi-val">{total_all.get("exact",0)}</div><div class="kpi-label">exact 匹配</div></div>
<div class="kpi"><div class="kpi-val">{total_all.get("rounded",0)}</div><div class="kpi-label">rounded (≤1%)</div></div>
<div class="kpi"><div class="kpi-val" style="color:#dc2626">{total_all.get("large_error",0)}</div><div class="kpi-label">large_error</div></div>
</div>

<div class="summary" style="border-left-color:#16a34a;background:#f0fdf4">
<strong>方法：</strong>用 <code>rules/tushare_rds_field_mapping.yaml</code>（144 条映射）将 tushare 英文字段名转为 RDS 中文名，然后直接匹配同名字段的值。
<strong>优势：</strong>不依赖 value-based 匹配，不会因"值接近但字段不同"而误匹配。
</div>

<h2>📈 汇总表</h2>
<table>
<thead><tr><th>股票</th><th>名称</th><th>板块</th><th>tushare</th><th>RDS</th><th>匹配</th><th>exact_rate</th>
<th>exact</th><th>sub_yuan</th><th>rounded</th><th>large_error</th>
<th>tushare 未匹配</th><th>RDS 未匹配</th></tr></thead>
<tbody>{"".join(summary_rows)}</tbody>
</table>

<div class="toc">
<strong>目录：</strong>
{" · ".join([f"<a href='#s{s}'>{s} {stocks_meta[s]}</a>" for s in ['600519','600887','000651','688981','300750','600036']])}
</div>

{body_html}

<hr style="margin:40px 0;border:none;border-top:1px solid #e2e8f0">
<div style="text-align:center;color:#a0aec0;font-size:12px">
Tushare vs RDS 综合对比报告 · 2026-06-12 · name-based mapping (144 rules)
</div>
</body></html>'''

out_path = 'docs/audit/2026-06-12-tushare-vs-rds-comprehensive.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Written {len(html)} bytes to {out_path}')
