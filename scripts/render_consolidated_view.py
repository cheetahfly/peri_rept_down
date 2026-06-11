# -*- coding: utf-8 -*-
"""
生成 600519 2020 年报 CF 各渠道数据汇总分列 HTML 表格。

布局：
  - 表头：item_code | item_name | RDS 标准 | 10 个 akshare 渠道
  - 行：49 个 RDS item（按 display_order 排序）
  - 每个渠道单元格显示：
      - 匹配到的字段名（小字）
      - 匹配值（同RDS：绿色 / 近似：黄色 / 大误差：红色 / 无数据：灰色）

输出：tmp/akshare_test_600519_2020/_consolidated_view.html
"""
import os
import json
import sys
import webbrowser
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from akshare_cf_test_compare import (  # noqa: E402
    extract_em_2020_values,
    extract_ths_old_2020_values,
    extract_ths_new_2020_values,
    extract_sina_2020_values,
    best_match,
    load_rds,
)

OUT_DIR = "tmp/akshare_test_600519_2020"
HTML_PATH = os.path.join(OUT_DIR, "_consolidated_view.html")

CHANNELS = [
    ("01 EM 年度",          "raw_01_em_yearly.csv",          extract_em_2020_values, "stock_cash_flow_sheet_by_yearly_em"),
    ("02 EM 单季度",        "raw_02_em_quarterly.csv",       extract_em_2020_values, "stock_cash_flow_sheet_by_quarterly_em (Q4单季)"),
    ("03 EM 报告期",        "raw_03_em_report.csv",          extract_em_2020_values, "stock_cash_flow_sheet_by_report_em"),
    ("04 EM 退市股接口",    "raw_04_em_report_delisted.csv", extract_em_2020_values, "stock_cash_flow_sheet_by_report_delisted_em"),
    ("05 THS旧 按报告期",   "raw_05_ths_old_report.csv",     extract_ths_old_2020_values, "stock_financial_cash_ths (按报告期)"),
    ("06 THS旧 按年度",     "raw_06_ths_old_yearly.csv",     extract_ths_old_2020_values, "stock_financial_cash_ths (按年度)"),
    ("07 THS旧 按单季度",   "raw_07_ths_old_single_q.csv",   extract_ths_old_2020_values, "stock_financial_cash_ths (按单季度)"),
    ("08 THS新 按报告期",   "raw_08_ths_new_report.csv",     extract_ths_new_2020_values, "stock_financial_cash_new_ths (按报告期)"),
    ("09 THS新 按年度",     "raw_09_ths_new_yearly.csv",     extract_ths_new_2020_values, "stock_financial_cash_new_ths (按年度)"),
    ("10 Sina",             "raw_10_sina_cf.csv",            extract_sina_2020_values, "stock_financial_report_sina (现金流量表)"),
]


def fmt_money(v):
    if v is None:
        return ""
    return f"{v:,.2f}"


def cell_class(abs_diff, rel_err, has_value, raw_match_was_best=True):
    """返回单元格 CSS class。"""
    if not has_value:
        return "no-data"
    if abs_diff < 0.01:
        return "exact"
    if abs_diff < 1.0:
        return "sub-yuan"
    if rel_err < 1.0:
        return "rounded"
    return "mismatch"


def main():
    rds = load_rds()
    rds_items = sorted(rds["items"], key=lambda x: x.get("display_order", 0))

    # 加载每个渠道
    channel_data = []
    for name, csv_file, extractor, api_sig in CHANNELS:
        path = os.path.join(OUT_DIR, csv_file)
        try:
            values = extractor(path)
        except Exception as e:
            values = {}
            print(f"[WARN] {name}: {e}")
        channel_data.append((name, api_sig, values))
        print(f"{name}: {len(values)} fields")

    # 生成 HTML
    indirect_codes = {"F044N","F046N","F047N","F048N","F050N","F051N","F053N","F054N",
                      "F055N","F056N","F057N","F058N","F060N","F066N","F067N","F071N","F096N"}

    # 头部表格
    rows_html = []
    for item in rds_items:
        rds_v = item["value"]
        if rds_v is None:
            continue
        is_indirect = item["item_code"] in indirect_codes
        row_class = "indirect-row" if is_indirect else ""

        tds = [
            f'<td class="code-cell">{item["item_code"]}</td>',
            f'<td class="name-cell">{"<span class=\"ind-tag\">间</span> " if is_indirect else ""}{item["item_name"]}</td>',
            f'<td class="rds-cell num">{fmt_money(rds_v)}</td>',
        ]
        for name, api_sig, values in channel_data:
            label, ch_v, diff, rel = best_match(rds_v, values)
            if label is None:
                tds.append('<td class="ch-cell no-data">—</td>')
                continue
            klass = cell_class(diff, rel, True)
            tooltip = f"匹配字段: {label}\\n差异: {diff:,.2f} 元 ({rel:.2f}%)"
            ch_disp = fmt_money(ch_v)
            ind_disp = f'<div class="match-label">{label[:30]}</div>' if klass != "no-data" else ''
            tds.append(
                f'<td class="ch-cell {klass}" title="{tooltip}">'
                f'<div class="num">{ch_disp}</div>{ind_disp}</td>'
            )
        rows_html.append(f'<tr class="{row_class}">' + "".join(tds) + "</tr>")

    # 表头
    ch_th = "".join(f'<th class="ch-th" title="{api}"><div>{name}</div></th>' for name, api, _ in channel_data)
    field_count_th = "".join(
        f'<th class="ch-th sub-th">{len(v)}个字段</th>'
        for _, _, v in channel_data
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>600519 2020 现金流量表 — 各渠道汇总分列对比</title>
<style>
* {{ box-sizing: border-box; }}
body {{
    font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif;
    margin: 0; padding: 0;
    background: #f5f6f8; color: #24292e;
    font-size: 13px;
}}
header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: #fff; padding: 24px 32px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}}
header h1 {{ margin: 0 0 6px 0; font-size: 22px; }}
header .meta {{ font-size: 12px; opacity: 0.85; }}
.warning-banner {{
    background: #fff8db; border-left: 4px solid #f0ad4e;
    padding: 12px 20px; margin: 16px 32px; border-radius: 4px;
    font-size: 13px; color: #5c4006;
}}
.warning-banner strong {{ color: #b35900; }}
.legend {{
    background: #fff; margin: 16px 32px; padding: 12px 20px;
    border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    display: flex; gap: 24px; flex-wrap: wrap; align-items: center;
    font-size: 12px;
}}
.legend-item {{ display: inline-flex; align-items: center; gap: 6px; }}
.legend-box {{ width: 18px; height: 18px; border-radius: 3px; display: inline-block; }}
.box-exact {{ background: #c8eac8; }}
.box-sub {{ background: #f4e4b4; }}
.box-rounded {{ background: #ffe0a3; }}
.box-mismatch {{ background: #f5c2c2; }}
.box-no {{ background: #e8e8e8; }}
.box-ind {{ background: #e3d4f5; border: 1px solid #b89ce8; }}

.table-wrap {{
    margin: 16px 32px 32px 32px;
    background: #fff; border-radius: 8px; overflow: auto;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    max-height: 80vh;
}}
table {{
    border-collapse: separate; border-spacing: 0;
    width: 100%; min-width: 2400px;
}}
thead th {{
    position: sticky; top: 0; z-index: 10;
    background: #1a1a2e; color: #fff;
    padding: 10px 8px; text-align: center;
    font-weight: 600; font-size: 12px;
    border-bottom: 2px solid #16213e;
}}
thead .sub-th {{
    background: #16213e; top: 38px;
    font-size: 11px; font-weight: normal; opacity: 0.85;
}}
tbody td {{
    padding: 8px 10px; border-bottom: 1px solid #f0f3f6;
    vertical-align: top;
}}
.code-cell {{
    font-family: "Consolas", monospace; color: #6a737d;
    background: #fafbfc; font-size: 11px;
    position: sticky; left: 0; z-index: 5;
    border-right: 1px solid #e1e4e8;
    min-width: 70px;
}}
.name-cell {{
    color: #24292e; min-width: 230px;
    position: sticky; left: 70px; z-index: 5;
    background: #fafbfc; border-right: 1px solid #e1e4e8;
}}
.rds-cell {{
    background: #e8f4ff; font-weight: 600; color: #0366d6;
    border-right: 2px solid #0366d6; min-width: 160px;
    position: sticky; left: 300px; z-index: 5;
}}
.ch-cell {{
    min-width: 175px; text-align: right;
    border-right: 1px solid #f0f3f6;
}}
.ch-cell .num {{
    font-family: "Consolas", "SF Mono", monospace;
    font-size: 12px; white-space: nowrap;
}}
.match-label {{
    font-size: 10px; color: #888;
    margin-top: 2px; text-align: left;
    word-break: break-all; line-height: 1.3;
}}
.exact {{ background: #c8eac8; }}
.exact .num {{ color: #1e7a1e; font-weight: 600; }}
.sub-yuan {{ background: #f4e4b4; }}
.rounded {{ background: #ffe0a3; }}
.rounded .num {{ color: #8a5a00; }}
.mismatch {{ background: #f5c2c2; }}
.mismatch .num {{ color: #a02020; }}
.no-data {{ background: #e8e8e8; color: #999; text-align: center; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}

.indirect-row .name-cell {{ background: #f7f0ff; }}
.indirect-row .code-cell {{ background: #f7f0ff; }}
.ind-tag {{
    display: inline-block; background: #8a4fcf; color: #fff;
    font-size: 10px; padding: 1px 5px; border-radius: 3px;
    margin-right: 4px; vertical-align: middle;
}}

tbody tr:hover .ch-cell,
tbody tr:hover .name-cell,
tbody tr:hover .code-cell,
tbody tr:hover .rds-cell {{
    filter: brightness(0.97);
}}

footer {{
    text-align: center; color: #959da5; font-size: 11px;
    padding: 16px 0 32px 0;
}}
</style>
</head>
<body>
<header>
    <h1>600519 贵州茅台 — 2020 年报现金流量表各渠道汇总分列</h1>
    <div class="meta">
        测试日期: 2026-06-11 ｜
        RDS 基准: cninfo/data_backup/cf_o.rds ｜
        共 {len(rds_items)} 项 RDS item（含间接法 17 项）
    </div>
</header>

<div class="warning-banner">
    <strong>⚠ EM 精度不稳定提醒</strong>：本次测试中 600519 在 EM 渠道精确到分，但 EM
    渠道的精度<strong>因股票而异</strong>——部分上市公司精确到分，部分仅精确到百万元。
    与 THS 新版同样存在精度不稳定问题。结论不能简单外推到所有股票，使用前需对目标股票做精度验证。
</div>

<div class="legend">
    <span><strong>颜色图例：</strong></span>
    <span class="legend-item"><span class="legend-box box-exact"></span>精确到分（差异 &lt; 0.01元）</span>
    <span class="legend-item"><span class="legend-box box-sub"></span>差异 &lt; 1元</span>
    <span class="legend-item"><span class="legend-box box-rounded"></span>近似（相对误差 &lt; 1%）</span>
    <span class="legend-item"><span class="legend-box box-mismatch"></span>大误差或字段缺失</span>
    <span class="legend-item"><span class="legend-box box-no"></span>无匹配</span>
    <span class="legend-item"><span class="legend-box box-ind"></span><span class="ind-tag">间</span>RDS 间接法项目</span>
</div>

<div class="table-wrap">
<table>
<thead>
    <tr>
        <th rowspan="2" style="position:sticky;left:0;z-index:11;background:#1a1a2e;">RDS 字段码</th>
        <th rowspan="2" style="position:sticky;left:70px;z-index:11;background:#1a1a2e;">项目名称</th>
        <th rowspan="2" style="position:sticky;left:300px;z-index:11;background:#0366d6;color:#fff;">RDS 标准值 (元)</th>
        {ch_th}
    </tr>
    <tr>
        {field_count_th}
    </tr>
</thead>
<tbody>
{chr(10).join(rows_html)}
</tbody>
</table>
</div>

<footer>
Generated by <code>scripts/render_consolidated_view.py</code> ｜
Source data: <code>tmp/akshare_test_600519_2020/raw_*.csv</code>
</footer>
</body>
</html>
"""

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    abs_path = os.path.abspath(HTML_PATH)
    print(f"\nHTML saved: {abs_path}")
    url = "file:///" + abs_path.replace("\\", "/")
    print(f"Opening: {url}")
    webbrowser.open(url)


if __name__ == "__main__":
    main()
