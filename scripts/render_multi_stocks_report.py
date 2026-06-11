# -*- coding: utf-8 -*-
"""
生成多股多渠道精度稳定性 HTML 报告。

视图：
  - 上半：精度稳定性矩阵（5 股 × 5 渠道，精确率热力图）
  - 下半：每只股票一个折叠区，展示该股票在5渠道下的关键差异样本
"""
import os
import json
import webbrowser

OUT_DIR = "tmp/akshare_test_multi_stocks_2020"
JSON_PATH = os.path.join(OUT_DIR, "_compare_matrix.json")
HTML_PATH = os.path.join(OUT_DIR, "_multi_stocks_report.html")


def color_for(pct):
    """根据百分比返回CSS颜色等级。"""
    if pct >= 99: return "lvl-100"
    if pct >= 95: return "lvl-95"
    if pct >= 80: return "lvl-80"
    if pct >= 50: return "lvl-50"
    return "lvl-low"


def fmt_money(v):
    if v is None: return ""
    return f"{v:,.2f}"


def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    matrix = data["matrix"]
    details = data["details"]
    stocks = data["stocks"]
    channels = data["channels"]

    # --- 上半：精度矩阵 ---
    # 行=股票，列=渠道
    rows = []
    for code, name, board in stocks:
        cells = [f'<td class="stock-name"><strong>{code}</strong> {name}<br><small>{board}</small></td>']
        # RDS 项目总数（取该股第一个OK channel的指标）
        any_m = next((m for m in matrix if m["stock_code"]==code and m["status"]=="OK"), None)
        rds_total = (any_m["exact"] + any_m["sub_yuan"] + any_m["rounded"] + any_m["large_error"] + any_m["no_match"]) if any_m else 0
        cells.append(f'<td class="rds-total">{rds_total}</td>')
        for ch in channels:
            m = next((x for x in matrix if x["stock_code"]==code and x["channel"]==ch), None)
            if m is None or m["status"]!="OK":
                cells.append('<td class="fail">FAIL</td>')
                continue
            klass = color_for(m["exact_rate"])
            tip = (f"exact={m['exact']}, sub-yuan={m['sub_yuan']}, "
                   f"rounded={m['rounded']}, large_error={m['large_error']}, no_match={m['no_match']}\\n"
                   f"间接法精确: {m['indirect_exact_count']}/{m['indirect_total_rds']}")
            cells.append(
                f'<td class="rate-cell {klass}" title="{tip}">'
                f'<div class="big-pct">{m["exact_rate"]:.1f}%</div>'
                f'<div class="sub-pct">{m["exact"]}/{rds_total}</div>'
                f'<div class="ind-pct">间接 {m["indirect_exact_count"]}/{m["indirect_total_rds"]}</div>'
                f'</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")

    matrix_thead = '<th>股票</th><th>RDS<br>项目数</th>' + "".join(f'<th>{c}</th>' for c in channels)

    # --- 下半：每股每渠道详情 ---
    detail_blocks = []
    for code, name, board in stocks:
        ch_details = []
        for ch in channels:
            key = f"{code}_{ch}"
            if key not in details:
                ch_details.append(f'<div class="ch-block fail-block"><h4>{ch}</h4><p>下载失败，无数据</p></div>')
                continue
            ds = details[key]
            # 仅展示前 10 项 + 所有非 exact
            sample = ds[:5]
            non_exact = [d for d in ds if d["class"] != "exact"]
            shown = sample + [d for d in non_exact if d not in sample][:15]
            rows_html = []
            for d in shown:
                klass = d["class"]
                diff = d.get("abs_diff") or 0
                rel = d.get("rel_err_pct") or 0
                rows_html.append(
                    f'<tr class="row-{klass}">'
                    f'<td class="code-c">{d["rds_item_code"]}</td>'
                    f'<td class="name-c">{d["rds_item_name"][:30]}</td>'
                    f'<td class="num">{fmt_money(d["rds_value"])}</td>'
                    f'<td class="num">{fmt_money(d.get("ch_value"))}</td>'
                    f'<td class="num">{diff:,.2f}</td>'
                    f'<td class="num">{rel:.2f}%</td>'
                    f'<td class="match-label" title="{d.get("ch_label","")}">{(d.get("ch_label") or "")[:24]}</td>'
                    f'</tr>'
                )
            m = next((x for x in matrix if x["stock_code"]==code and x["channel"]==ch), {})
            ch_details.append(f"""
<div class="ch-block">
  <h4>{ch} — exact: {m.get('exact',0)}, sub-yuan: {m.get('sub_yuan',0)}, rounded: {m.get('rounded',0)}, large_error: {m.get('large_error',0)}</h4>
  <table class="detail-table">
    <thead><tr><th>code</th><th>项目</th><th>RDS</th><th>akshare</th><th>差异</th><th>误差%</th><th>匹配字段</th></tr></thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
</div>""")
        detail_blocks.append(f"""
<details class="stock-section">
<summary><strong>{code} {name}</strong> · {board}</summary>
{"".join(ch_details)}
</details>""")

    # 关键结论
    conclusion = """
<div class="conclusion-box">
  <h3>📌 关键结论：EM / THS 新版精度确实因股票而异</h3>
  <ul>
    <li><strong>000651 格力电器</strong>：100% 精确到分（理想情况）</li>
    <li><strong>600887 伊利股份</strong>：98.2% 精确到分（与 600519 一致，绝大多数项精确到分）</li>
    <li><strong>688981 中芯国际</strong>（科创板）：96.2% / 90.6% — RDS 数据精度本身就是<strong>千元</strong>级别，akshare 同步</li>
    <li><strong>600036 招商银行</strong>（金融股）：90.2% / 78.4% — 字段映射差异较大，<code>em_delisted</code> 直接报错</li>
    <li><strong>🔴 300750 宁德时代</strong>：<strong>0% 精确到分</strong>！EM/THS 新版返回值均<strong>精确到百元位</strong>（以 00 结尾，差异 0-50 元），是典型的"akshare 渠道在某只股票上降级精度"案例</li>
  </ul>
  <p><strong>结论</strong>：</p>
  <ol>
    <li>EM 与 THS 新版精度 <strong>不能信任为"始终到分"</strong>。使用任何 akshare 渠道作为数据源前，必须对目标股票做精度抽样校验。</li>
    <li>不同股票的 akshare 数据精度可能差异极大：从 <strong>个位 (元)</strong> 到 <strong>千位</strong> 到 <strong>百位</strong>。</li>
    <li><code>em_delisted</code> 接口对金融股调用直接报错，不适合通用调用。</li>
    <li>金融股 (招商银行) 的 CF 字段口径与非金融股不同，需专门处理映射。</li>
  </ol>
</div>
"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>akshare 多股多渠道精度稳定性测试 — 2020 年报现金流量表</title>
<style>
body {{ font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif;
        background: #f5f6f8; color: #24292e; margin: 0; padding: 0; font-size: 14px; }}
header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff;
         padding: 24px 32px; }}
header h1 {{ margin: 0 0 6px 0; font-size: 22px; }}
header .meta {{ font-size: 12px; opacity: 0.85; }}

.section {{ background: #fff; margin: 16px 32px; padding: 20px;
            border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.section h2 {{ margin-top: 0; color: #0366d6; border-bottom: 1px solid #e1e4e8; padding-bottom: 8px; }}

.matrix-table {{ width: 100%; border-collapse: collapse; }}
.matrix-table th {{ background: #1a1a2e; color: #fff; padding: 10px;
                     border-right: 1px solid #2c2c4e; font-size: 13px; text-align: center; }}
.matrix-table td {{ padding: 10px; text-align: center; border-right: 1px solid #f0f3f6;
                     border-bottom: 1px solid #f0f3f6; vertical-align: middle; }}
.stock-name {{ text-align: left !important; background: #fafbfc; min-width: 200px; }}
.stock-name small {{ color: #888; }}
.rds-total {{ background: #e8f4ff; color: #0366d6; font-weight: bold; }}
.rate-cell {{ font-family: "Consolas", monospace; min-width: 140px; cursor: help; }}
.big-pct {{ font-size: 22px; font-weight: bold; }}
.sub-pct {{ font-size: 11px; color: #555; }}
.ind-pct {{ font-size: 11px; color: #6b3fa0; }}

.lvl-100 {{ background: #c8eac8; color: #1e7a1e; }}
.lvl-95 {{ background: #d9efbf; color: #38780b; }}
.lvl-80 {{ background: #f4e4b4; color: #8a5a00; }}
.lvl-50 {{ background: #ffcfaf; color: #a04a00; }}
.lvl-low {{ background: #f5b6b6; color: #a02020; }}
.fail {{ background: #444; color: #fff; font-weight: bold; }}

.conclusion-box {{ background: #fff8db; border-left: 4px solid #f0ad4e;
                    padding: 16px 20px; margin: 16px 32px; border-radius: 4px; }}
.conclusion-box h3 {{ margin-top: 0; color: #b35900; }}
.conclusion-box code {{ background: #f1f3f5; padding: 1px 5px; border-radius: 3px;
                         color: #d73a49; font-size: 13px; }}

.stock-section {{ margin: 16px 32px; background: #fff; border-radius: 8px;
                   box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 0 20px 16px 20px; }}
.stock-section summary {{ padding: 14px 0; cursor: pointer; font-size: 15px;
                          border-bottom: 1px solid #e1e4e8; }}
.stock-section summary:hover {{ color: #0366d6; }}
.ch-block {{ margin: 16px 0; }}
.ch-block h4 {{ margin: 8px 0; color: #2c3e50; font-size: 13px;
                background: #f6f8fa; padding: 6px 10px; border-radius: 4px; }}
.fail-block {{ color: #a02020; }}

.detail-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
.detail-table th {{ background: #f6f8fa; padding: 6px 8px; text-align: left;
                     border-bottom: 1px solid #e1e4e8; font-size: 12px; }}
.detail-table td {{ padding: 5px 8px; border-bottom: 1px solid #f0f3f6; }}
.code-c {{ font-family: monospace; color: #888; font-size: 11px; }}
.name-c {{ max-width: 220px; }}
.num {{ text-align: right; font-family: "Consolas", monospace; font-variant-numeric: tabular-nums; }}
.match-label {{ font-size: 11px; color: #888; }}

.row-exact td:nth-child(n+3) {{ background: #f0fbf0; }}
.row-sub_yuan td:nth-child(n+3) {{ background: #fef9e0; }}
.row-rounded td:nth-child(n+3) {{ background: #ffefd0; }}
.row-large_error td:nth-child(n+3) {{ background: #ffd8d8; }}
.row-no_match td:nth-child(n+3) {{ background: #eaeaea; }}

footer {{ text-align: center; color: #959da5; font-size: 11px; padding: 16px 0 32px 0; }}
</style>
</head>
<body>
<header>
    <h1>akshare 多股多渠道精度稳定性测试 — 2020 年报现金流量表</h1>
    <div class="meta">
        测试日期 2026-06-11 ｜
        5 只股票 × 5 渠道 = 25 次调用 ｜
        基准: cninfo RDS (cf_o.rds / cf_f.rds)
    </div>
</header>

{conclusion}

<div class="section">
<h2>1. 精度稳定性矩阵</h2>
<p style="color:#666;font-size:12px;">每格大字 = 精确到分(<0.01元)的比率；下方"间接 X/Y" = 间接法补充资料项目精确匹配数</p>
<table class="matrix-table">
<thead><tr>{matrix_thead}</tr></thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
<p style="font-size:11px;color:#888;margin-top:12px;">
颜色等级：<span class="lvl-100" style="padding:2px 6px;">≥99%</span>
<span class="lvl-95" style="padding:2px 6px;">95-99%</span>
<span class="lvl-80" style="padding:2px 6px;">80-95%</span>
<span class="lvl-50" style="padding:2px 6px;">50-80%</span>
<span class="lvl-low" style="padding:2px 6px;">&lt;50%</span>
<span class="fail" style="padding:2px 6px;">FAIL</span>
</p>
</div>

<div class="section">
<h2>2. 每只股票每渠道详情（点击展开）</h2>
<p style="color:#666;font-size:12px;">行底色：绿=精确到分，黄=&lt;1元，橙=&lt;1%误差，红=大误差/字段缺失</p>
{"".join(detail_blocks)}
</div>

<footer>
Generated by <code>scripts/render_multi_stocks_report.py</code> ·
data: <code>{OUT_DIR}/raw_*.csv</code>
</footer>
</body>
</html>"""

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    abs_path = os.path.abspath(HTML_PATH)
    print(f"HTML saved: {abs_path}")
    url = "file:///" + abs_path.replace("\\", "/")
    print(f"Opening: {url}")
    webbrowser.open(url)


if __name__ == "__main__":
    main()
