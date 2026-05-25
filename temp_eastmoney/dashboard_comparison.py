# -*- coding: utf-8 -*-
"""
生成多股票多期对比看板
从 batch_data 读取已下载数据，输出跨期跨公司对比HTML
"""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em_common import format_value

BASE = os.path.dirname(os.path.abspath(__file__))
BATCH_DIR = os.path.join(BASE, "batch_data")

STOCK_NAMES = {
    "000001": "平安银行", "000333": "美的集团", "000858": "五粮液",
    "002415": "海康威视", "002475": "立讯精密", "300750": "宁德时代",
    "600036": "招商银行", "600519": "贵州茅台", "600887": "伊利股份",
    "601318": "中国平安",
}


def load_all_data():
    """遍历batch_data加载所有已下载的摘要数据"""
    records = []
    if not os.path.isdir(BATCH_DIR):
        print(f"batch_data目录不存在: {BATCH_DIR}")
        return records

    for code in sorted(os.listdir(BATCH_DIR)):
        code_dir = os.path.join(BATCH_DIR, code)
        if not os.path.isdir(code_dir):
            continue
        for period_dir in sorted(os.listdir(code_dir)):
            summary_path = os.path.join(code_dir, period_dir, "summary.json")
            if not os.path.exists(summary_path):
                continue
            # 从目录名解析: e.g., 2020_一季报 -> (2020, "一季报")
            try:
                year_str, period_cn = period_dir.split("_", 1)
                year = int(year_str)
            except (ValueError, IndexError):
                continue
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records.append({
                "code": code,
                "year": year,
                "period": period_cn,
                "label": f"{year}年{period_cn}",
                "data": data,
            })
    return records


def get_key_metrics():
    """定义跨期对比的核心指标"""
    return {
        "利润表": {
            "en": "income_statement",
            "metrics": [
                ("营业收入", "营业收入"),
                ("归母净利润", "归母净利润"),
                ("扣非归母净利润", "扣非归母净利润"),
                ("营业利润", "营业利润"),
                ("毛利率", None),  # 计算项
                ("净利率", None),
            ],
        },
        "资产负债表": {
            "en": "balance_sheet",
            "metrics": [
                ("资产总计", "资产总计"),
                ("负债合计", "负债合计"),
                ("所有者权益合计", "所有者权益合计"),
                ("资产负债率", None),
                ("货币资金", "货币资金"),
                ("应收账款", "应收账款"),
                ("存货", "存货"),
            ],
        },
        "现金流量表": {
            "en": "cash_flow",
            "metrics": [
                ("经营活动现金流净额", "经营活动现金流净额"),
                ("投资活动现金流净额", "投资活动现金流净额"),
                ("筹资活动现金流净额", "筹资活动现金流净额"),
                ("现金净增加额", "现金净增加额"),
            ],
        },
    }


def compute_metric(metric_cn, en_name, data):
    """计算指标值，支持直接字段和计算字段"""
    stmt = data.get(en_name, {})
    kf = stmt.get("key_fields", {}) if stmt else {}

    if metric_cn == "毛利率":
        rev = float(kf.get("营业收入", 0) or 0)
        cost = float(kf.get("营业成本", 0) or 0)
        return (rev - cost) / rev * 100 if rev else None
    elif metric_cn == "净利率":
        rev = float(kf.get("营业收入", 0) or 0)
        np = float(kf.get("归母净利润", 0) or 0)
        return np / rev * 100 if rev else None
    elif metric_cn == "资产负债率":
        assets = float(kf.get("资产总计", 0) or 0)
        liab = float(kf.get("负债合计", 0) or 0)
        return liab / assets * 100 if assets else None
    else:
        val = kf.get(metric_cn)
        return float(val) if val else None


def fmt_val(val, metric_cn=None):
    """格式化指标值"""
    if val is None:
        return "N/A"
    if metric_cn in ("毛利率", "净利率", "资产负债率"):
        return f"{val:.2f}%"
    return format_value(val)


def generate_html(records):
    """生成对比看板HTML"""
    stocks = sorted(set(r["code"] for r in records))
    years = sorted(set(r["year"] for r in records))
    stmt_defs = get_key_metrics()

    html_parts = []
    html_parts.append('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>A股财务数据对比看板</title>
<style>
  body { font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f5f7fa; margin:0; padding:20px; color:#333; }
  h1 { text-align:center; color:#1a1a2e; margin-bottom:5px; font-size:22px; }
  .subtitle { text-align:center; color:#888; margin-bottom:25px; font-size:13px; }
  .container { max-width:1400px; margin:0 auto; }
  .stock-section { background:#fff; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.08); margin-bottom:25px; overflow:hidden; }
  .stock-hdr { padding:14px 20px; font-size:16px; font-weight:bold; color:#fff; display:flex; justify-content:space-between; align-items:center;
               background:linear-gradient(135deg,#667eea,#764ba2); }
  .stock-hdr .info { font-size:12px; font-weight:normal; opacity:0.9; }
  .table-wrap { overflow-x:auto; padding:0; }
  table { width:100%; border-collapse:collapse; font-size:12px; }
  th { background:#f8f9fc; padding:8px 12px; text-align:center; border-bottom:2px solid #eee; position:sticky; top:0; white-space:nowrap; }
  th.stmt-header { background:#eef1f8; color:#555; font-size:13px; }
  td { padding:6px 12px; border-bottom:1px solid #f0f0f0; text-align:center; white-space:nowrap; }
  td.metric-name { text-align:left; font-weight:500; background:#fafbfc; position:sticky; left:0; min-width:140px; }
  tr:hover td { background:#f8f9ff; }
  tr:hover td.metric-name { background:#eef0f8; }
  .val-pos { color:#27ae60; }
  .val-neg { color:#e74c3c; }
  .val-na { color:#bbb; }
  .year-mark { background:#f0f2f5; font-weight:bold; }
  .footer { text-align:center; color:#aaa; font-size:11px; margin-top:20px; padding:15px; }
  .tabs { display:flex; gap:10px; justify-content:center; margin-bottom:20px; }
  .tabs a { padding:8px 20px; background:#fff; border-radius:6px; box-shadow:0 1px 4px rgba(0,0,0,0.1);
            color:#555; text-decoration:none; font-size:13px; }
  .tabs a:hover { background:#667eea; color:#fff; }
</style>
</head>
<body>
<div class="container">
<h1>A股财务数据对比看板</h1>
<div class="subtitle">数据来源: 东方财富数据中心 | 单位: 元 (比率除外) | 生成时间: ''' + __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M") + '''</div>

<div class="tabs">
  <a href="#overview">综合概览</a>
  <a href="#income">利润表</a>
  <a href="#balance">资产负债表</a>
  <a href="#cashflow">现金流量表</a>
</div>
''')

    # 为每只股票生成三个报表的跨期对比表
    for code in stocks:
        stock_records = [r for r in records if r["code"] == code]
        code_dir = os.path.join(BATCH_DIR, code)
        # 尝试从目录下的第一个summary获取股票名
        stock_name = code
        for r in stock_records:
            for stmt in r["data"].values():
                if stmt and stmt.get("报表名称"):
                    # 无法直接获取股票名，就用code
                    pass
                    break

        name_display = STOCK_NAMES.get(code, code)
        html_parts.append(f'''
<div class="stock-section" id="{code}">
<div class="stock-hdr">
  <span>{code} {name_display}</span>
  <span class="info">已下载 {len(stock_records)} 个报告期</span>
</div>''')

        # 按年份排序
        periods_order = {"一季报": 1, "半年报": 2, "三季报": 3, "年报": 4}
        stock_records.sort(key=lambda r: (r["year"], periods_order.get(r["period"], 99)))

        # 生成三个报表的子表
        for stmt_cn, stmt_cfg in stmt_defs.items():
            en = stmt_cfg["en"]
            metrics = stmt_cfg["metrics"]

            html_parts.append(f'''
<div class="table-wrap">
<table>
<thead>
<tr><th class="stmt-header" colspan="{len(stock_records) + 1}">{stmt_cn}</th></tr>
<tr><th>指标</th>''')
            for r in stock_records:
                html_parts.append(f'<th>{r["label"]}</th>')
            html_parts.append('</tr></thead><tbody>')

            for metric_cn, field_name in metrics:
                html_parts.append(f'<tr><td class="metric-name">{metric_cn}</td>')
                for r in stock_records:
                    val = compute_metric(field_name or metric_cn, en, r["data"])
                    if val is not None:
                        cls = "val-pos" if val > 0 else ("val-neg" if val < 0 else "")
                        html_parts.append(f'<td class="{cls}">{fmt_val(val, metric_cn)}</td>')
                    else:
                        html_parts.append('<td class="val-na">N/A</td>')
                html_parts.append('</tr>')

            html_parts.append('</tbody></table></div>')

        html_parts.append('</div>')

    html_parts.append('''
<div class="footer">
  数据: 东方财富数据中心 | 报告期含年报/半年报/一季报/三季报 | 累进数据口径
</div>
</div>
</body>
</html>''')

    return "\n".join(html_parts)


def main():
    records = load_all_data()
    print(f"共加载 {len(records)} 条记录")

    if not records:
        print("没有数据，请先运行 batch_download.py")
        return

    codes = set(r["code"] for r in records)
    years = set(r["year"] for r in records)
    print(f"覆盖 {len(codes)} 只股票，{len(years)} 个年份")

    html = generate_html(records)
    out_path = os.path.join(BASE, "dashboard_comparison.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"看板已生成: {out_path} ({os.path.getsize(out_path)/1024:.0f}KB)")


if __name__ == "__main__":
    main()
