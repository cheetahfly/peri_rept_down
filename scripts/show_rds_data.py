# -*- coding: utf-8 -*-
"""Load 600519 RDS data and generate HTML display."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extraction.ground_truth.rds_loader import RdsLoader

loader = RdsLoader("D:/Research/Quant/SETL/cninfo/data_backup")

stock_code = "600519"
year = 2020

st_labels = {
    "balance_sheet": "资产负债表 (Balance Sheet)",
    "income_statement": "利润表 (Income Statement)",
    "cash_flow": "现金流量表 (Cash Flow)",
}

html_parts = []

html_parts.append("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>600519 贵州茅台 2020 RDS标准数据</title>
<style>
body { font-family: -apple-system, "Microsoft YaHei", sans-serif; margin: 20px; background: #f5f5f5; color: #333; }
h1 { color: #1a1a2e; border-bottom: 3px solid #1a1a2e; padding-bottom: 8px; }
.st-card { background: #fff; border-radius: 8px; margin: 16px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; }
.st-header { padding: 12px 16px; font-weight: bold; font-size: 16px; background: #e3f2fd; border-bottom: 1px solid #bbdefb; display: flex; justify-content: space-between; }
.st-body { padding: 0; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #f5f7fa; padding: 8px 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #e0e0e0; }
td { padding: 6px 12px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
tr:hover { background: #fafbff; }
.num { text-align: right; font-family: "SF Mono", "Courier New", monospace; white-space: nowrap; }
.code { color: #888; font-size: 11px; font-family: monospace; }
.money { text-align: right; font-family: "SF Mono", "Courier New", monospace; white-space: nowrap; }
.order { color: #aaa; font-size: 11px; }
.section-row { background: #f0f4ff !important; font-weight: 600; }
.section-row td { border-top: 2px solid #90caf9; }
.section-label { font-size: 11px; color: #1565c0; margin-left: 8px; }
.summary { background: #fff; border-radius: 8px; padding: 16px; margin: 16px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.stat-box { text-align: center; padding: 12px; border-radius: 6px; background: #e8f5e9; }
.stat-box .num { font-size: 22px; font-weight: bold; display: block; color: #2e7d32; }
.stat-box .label { font-size: 12px; color: #666; }
@media print { body { background: #fff; } .st-card { break-inside: avoid; } }
</style>
</head>
<body>
<h1>600519 贵州茅台 — 2020年RDS标准数据</h1>
<p style="color:#666;">数据来源: D:/Research/Quant/SETL/cninfo/data_backup | 非金融企业表 (pl_o/b_o/cf_o)</p>
""")

total_items = 0
for st in ["income_statement", "balance_sheet", "cash_flow"]:
    tidy = loader.load_stock_data_tidy(stock_code, year, st)
    if not tidy:
        html_parts.append(f'<div class="st-card"><div class="st-header">{st_labels[st]}</div><div class="st-body" style="padding:16px;color:#999;">无数据</div></div>')
        continue

    total_items += len(tidy)

    # Determine sections if any
    sections = {}
    for item in tidy:
        name = item["item_name"]
        # Detect section headers (Chinese numbered items like "一、", "二、")
        for prefix in ["一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、", "九、", "十、"]:
            if name.startswith(prefix):
                sections[item["display_order"]] = name
                break

    html_parts.append(f'<div class="st-card">')
    html_parts.append(f'<div class="st-header"><span>{st_labels[st]}</span><span>{len(tidy)} 项</span></div>')
    html_parts.append('<div class="st-body"><table>')
    html_parts.append('<tr><th style="width:40px">#</th><th style="width:80px">编码</th><th>科目名称</th><th style="width:180px">值(元)</th></tr>')

    for i, item in enumerate(tidy, 1):
        name = item["item_name"]
        code = item["item_code"]
        val = item["value"]
        order = item["display_order"]

        # Check if this is a section header
        row_class = ""
        is_section = False
        for prefix in ["一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、", "九、", "十、"]:
            if name.startswith(prefix):
                row_class = ' class="section-row"'
                is_section = True
                break

        val_str = f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)

        html_parts.append(f'<tr{row_class}>')
        html_parts.append(f'<td class="order">{order}</td>')
        html_parts.append(f'<td class="code">{code}</td>')
        html_parts.append(f'<td>{name}</td>')
        html_parts.append(f'<td class="money">{val_str}</td>')
        html_parts.append('</tr>')
    html_parts.append('</table></div></div>')

# Summary
html_parts.append(f"""
<div class="summary">
  <h3>总览</h3>
  <div class="summary-grid">
    <div class="stat-box"><span class="num">{total_items}</span><span class="label">总科目数</span></div>
    <div class="stat-box"><span class="num">3</span><span class="label">报表类型</span></div>
    <div class="stat-box"><span class="num">2020</span><span class="label">年度</span></div>
  </div>
</div>
""")

html_parts.append("""
<p style="text-align:center;color:#999;font-size:12px;margin-top:30px;">
  RDS标准数据 | 展示顺序 = field_order.yaml 定义 | 编码映射 = decode_mappings_by_type.json
</p>
</body>
</html>""")

out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "phase2_reports", "600519_rds_data.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(html_parts))

print(f"HTML written to {out_path}")
print(f"Total items: {total_items}")
