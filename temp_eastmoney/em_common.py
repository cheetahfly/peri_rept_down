# -*- coding: utf-8 -*-
"""
东方财富API通用模块 - 供各报表子项目共用
支持：年报(001)、半年报(002)、一季报(003)、三季报(004)
"""
import requests, json, os, re
from datetime import datetime

BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}

DATE_TYPES = {
    "001": "年报",
    "002": "半年报",
    "003": "一季报",
    "004": "三季报",
}

# 三大报表API定义
REPORT_DEFS = {
    "income_statement": {
        "name": "利润表",
        "report_name": "RPT_DMSK_FN_INCOME",
        "columns": "ALL",
    },
    "balance_sheet": {
        "name": "资产负债表",
        "report_name": "RPT_DMSK_FN_BALANCE",
        "columns": "ALL",
    },
    "cash_flow": {
        "name": "现金流量表",
        "report_name": "RPT_DMSK_FN_CASHFLOW",
        "columns": "ALL",
    },
}


def fetch_report(report_type, security_code="002475",
                 date_type_code="001", report_date=None):
    """
    从东方财富下载指定报表

    Parameters:
        report_type: "income_statement" / "balance_sheet" / "cash_flow"
        security_code: 股票代码, 默认002475(立讯精密)
        date_type_code: 001=年报, 002=半年报, 003=一季报, 004=三季报
        report_date: 可选, 精确匹配报表日期 (如 "2025-06-30")
    Returns:
        (item_dict, error_msg) 成功返回(item, None), 失败返回(None, error)
    """
    cfg = REPORT_DEFS.get(report_type)
    if not cfg:
        return None, f"未知报表类型: {report_type}"

    # API不支持在filter中使用REPORT_DATE, 只能通过程序过滤
    filter_str = f'(SECURITY_CODE="{security_code}")'

    params = {
        "reportName": cfg["report_name"],
        "columns": cfg["columns"],
        "filter": filter_str,
        "pageNumber": 1,
        "pageSize": 30,
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
    }
    try:
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        data = r.json()
    except Exception as e:
        return None, f"请求失败: {e}"

    if not data.get("success"):
        return None, data.get("message", "API返回失败")

    items = data.get("result", {}).get("data", [])

    # 先用DATE_TYPE_CODE + REPORT_DATE双重匹配
    for item in items:
        dt = str(item.get("DATE_TYPE_CODE", ""))
        rd = str(item.get("REPORT_DATE", ""))
        if dt == date_type_code:
            if report_date:
                if report_date in rd:
                    return item, None
            else:
                return item, None

    # 回退: 只匹配DATE_TYPE_CODE (取最新的)
    for item in items:
        dt = str(item.get("DATE_TYPE_CODE", ""))
        if dt == date_type_code:
            return item, None

    # 回退: 只匹配report_date
    if report_date:
        for item in items:
            rd = str(item.get("REPORT_DATE", ""))
            if report_date in rd:
                return item, None

    return None, f"未找到 {DATE_TYPES.get(date_type_code, date_type_code)} 数据"


def get_key_fields(report_type):
    """获取各报表的关键字段映射"""
    if report_type == "income_statement":
        return {
            "营业收入": "TOTAL_OPERATE_INCOME",
            "营业成本": "TOTAL_OPERATE_COST",
            "营业利润": "OPERATE_PROFIT",
            "利润总额": "TOTAL_PROFIT",
            "所得税": "INCOME_TAX",
            "归母净利润": "PARENT_NETPROFIT",
            "扣非归母净利润": "DEDUCT_PARENT_NETPROFIT",
            "销售费用": "SALE_EXPENSE",
            "管理费用": "MANAGE_EXPENSE",
            "财务费用": "FINANCE_EXPENSE",
            "投资收益": "INVEST_INCOME",
            "营业税金及附加": "OPERATE_TAX_ADD",
            "基本每股收益": "BASIC_EPS",
            "研发费用": "RESEARCH_EXPENSE",
        }
    elif report_type == "balance_sheet":
        return {
            "资产总计": "TOTAL_ASSETS",
            "负债合计": "TOTAL_LIABILITIES",
            "所有者权益合计": "TOTAL_EQUITY",
            "货币资金": "MONETARYFUNDS",
            "应收账款": "ACCOUNTS_RECE",
            "存货": "INVENTORY",
            "固定资产": "FIXED_ASSET",
            "应付账款": "ACCOUNTS_PAYABLE",
            "短期借款": "SHORT_LOAN",
            "长期借款": "LONG_LOAN",
        }
    elif report_type == "cash_flow":
        return {
            "经营活动现金流净额": "NETCASH_OPERATE",
            "销售商品提供劳务收到的现金": "SALES_SERVICES",
            "投资活动现金流净额": "NETCASH_INVEST",
            "筹资活动现金流净额": "NETCASH_FINANCE",
            "现金净增加额": "CCE_ADD",
            "期初现金余额": "BEGIN_CCE",
            "期末现金余额": "END_CCE",
        }
    return {}


def list_all_fields(item, exclude_meta=True):
    """列出报表item中所有非空数值字段"""
    meta_fields = {
        "SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "INDUSTRY_CODE",
        "ORG_CODE", "INDUSTRY_NAME", "MARKET", "SECURITY_TYPE_CODE",
        "TRADE_MARKET_CODE", "DATE_TYPE_CODE", "REPORT_TYPE_CODE",
        "DATA_STATE", "NOTICE_DATE", "REPORT_DATE", "STD_REPORT_DATE",
        "CURRENCY", "CURRENCY_CODE", "IS_SHOW",
    }
    fields = []
    for k, v in item.items():
        if v is None:
            continue
        if exclude_meta and k in meta_fields:
            continue
        fields.append((k, v))
    return fields


def format_value(val):
    """格式化数值为可读形式"""
    if val is None:
        return "N/A"
    try:
        num = float(val)
        if abs(num) >= 1e8:
            return f"{num:,.2f} ({num/1e8:.2f}亿)"
        elif abs(num) >= 1e4:
            return f"{num:,.2f} ({num/1e4:.2f}万)"
        else:
            return f"{num:,.2f}"
    except (ValueError, TypeError):
        return str(val)


def format_value_plain(val):
    """仅返回纯数字格式"""
    if val is None:
        return "N/A"
    try:
        return f"{float(val):,.2f}"
    except (ValueError, TypeError):
        return str(val)


def validate_item(item, report_type):
    """
    对关键数据做合理性检查
    Returns: list of (field, status, detail)
    """
    checks = []
    if report_type == "balance_sheet":
        total_assets = safe_float(item.get("TOTAL_ASSETS"))
        total_liab = safe_float(item.get("TOTAL_LIABILITIES"))
        total_eq = safe_float(item.get("TOTAL_EQUITY"))
        if total_assets and total_liab is not None and total_eq is not None:
            diff = abs(total_assets - total_liab - total_eq)
            ratio = diff / total_assets if total_assets else 0
            if ratio < 0.01:
                checks.append(("会计恒等式", "OK",
                    f"资产={total_assets/1e8:.2f}亿 = 负债={total_liab/1e8:.2f}亿 + 权益={total_eq/1e8:.2f}亿"))
            else:
                checks.append(("会计恒等式", "偏差",
                    f"差值={diff/1e8:.2f}亿 (占比{ratio*100:.4f}%)"))

    elif report_type == "income_statement":
        revenue = safe_float(item.get("TOTAL_OPERATE_INCOME"))
        cost = safe_float(item.get("TOTAL_OPERATE_COST"))
        profit = safe_float(item.get("OPERATE_PROFIT"))
        netprofit = safe_float(item.get("PARENT_NETPROFIT"))
        if revenue and cost:
            gross = (revenue - cost) / revenue * 100
            checks.append(("毛利率", "OK" if gross > 0 else "异常",
                f"{gross:.2f}%"))
        if netprofit and revenue and revenue > 0:
            margin = netprofit / revenue * 100
            checks.append(("净利率", "OK",
                f"{margin:.2f}%"))

    elif report_type == "cash_flow":
        operate = safe_float(item.get("NETCASH_OPERATE"))
        invest = safe_float(item.get("NETCASH_INVEST"))
        finance = safe_float(item.get("NETCASH_FINANCE"))
        cce_add = safe_float(item.get("CCE_ADD"))
        if all(x is not None for x in [operate, invest, finance, cce_add]):
            calc_sum = operate + invest + finance
            diff = abs(calc_sum - cce_add)
            ratio = diff / abs(cce_add) if cce_add else diff
            ok = ratio < 0.01 or diff < 1e7  # 比值<1%或绝对值<1千万
            checks.append(("现金流勾稽", "OK" if ok else "偏差",
                f"经营{operate/1e8:.2f}亿+投资{invest/1e8:.2f}亿+筹资{finance/1e8:.2f}亿=净增{calc_sum/1e8:.2f}亿 (报表{cce_add/1e8:.2f}亿 差{ratio*100:.3f}%)"))

    return checks


def safe_float(val):
    """安全转换为float"""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def generate_html(data, report_name, period_label, out_dir):
    """
    生成HTML报表
    data: { "income_statement": item, "balance_sheet": item, "cash_flow": item }
    """
    html_parts = []
    html_parts.append(f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>立讯精密(002475) {period_label} - 三大财务报表</title>
<style>
  body {{ font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f5f7fa; margin:0; padding:20px; color:#333; }}
  h1 {{ text-align:center; color:#1a1a2e; margin-bottom:5px; font-size:22px; }}
  .subtitle {{ text-align:center; color:#888; margin-bottom:25px; font-size:13px; }}
  .container {{ max-width:1200px; margin:0 auto; }}
  .stmt {{ background:#fff; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.08); margin-bottom:25px; overflow:hidden; }}
  .hdr {{ padding:14px 20px; font-size:16px; font-weight:bold; color:#fff; display:flex; justify-content:space-between; align-items:center; }}
  .hdr-is {{ background:linear-gradient(135deg,#667eea,#764ba2); }}
  .hdr-bs {{ background:linear-gradient(135deg,#f093fb,#f5576c); }}
  .hdr-cf {{ background:linear-gradient(135deg,#4facfe,#00f2fe); }}
  .hdr .info {{ font-size:12px; font-weight:normal; opacity:0.9; }}
  .count {{ padding:8px 20px; background:#fafafa; border-bottom:1px solid #eee; font-size:12px; color:#999; }}
  .table-wrap {{ max-height:600px; overflow-y:auto; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ background:#f8f9fc; padding:10px 20px; text-align:left; font-size:12px; color:#888; border-bottom:2px solid #eee; position:sticky; top:0; }}
  th:last-child {{ text-align:right; }}
  td {{ padding:6px 20px; border-bottom:1px solid #f0f0f0; font-size:13px; }}
  td:last-child {{ text-align:right; color:#d63031; font-weight:500; }}
  tr:hover {{ background:#f8f9ff; }}
  .verify {{ display:inline-block; background:#00b894; color:#fff; padding:2px 8px; border-radius:3px; font-size:11px; margin-left:8px; }}
  .verify-warn {{ background:#fdcb6e; color:#fff; }}
  .checks {{ padding:12px 20px; background:#f8f9fc; border-top:1px solid #eee; font-size:12px; }}
  .checks span {{ display:inline-block; margin-right:15px; }}
  .checks .ok {{ color:#00b894; }}
  .checks .warn {{ color:#fdcb6e; }}
  .footer {{ text-align:center; color:#aaa; font-size:11px; margin-top:20px; padding:15px; }}
</style>
</head>
<body>
<div class="container">
<h1>立讯精密工业股份有限公司</h1>
<div class="subtitle">002475 | {period_label} | 数据来源: 东方财富数据中心</div>
''')

    stmt_defs = [
        ("income_statement", "利润表", "hdr-is"),
        ("balance_sheet", "资产负债表", "hdr-bs"),
        ("cash_flow", "现金流量表", "hdr-cf"),
    ]

    for en_name, cn_name, color_class in stmt_defs:
        item = data.get(en_name)
        if not item:
            continue

        # Collect all value fields
        all_fields = list_all_fields(item)
        # Build rows
        rows = []
        for f_name, f_val in sorted(all_fields, key=lambda x: x[0]):
            rows.append(
                f'<tr><td>{f_name}</td><td>{format_value_plain(f_val)}</td></tr>'
            )

        # Validation checks
        checks = validate_item(item, en_name)
        checks_html = ""
        if checks:
            check_items = []
            for field, status, detail in checks:
                cls = "ok" if status == "OK" else "warn"
                check_items.append(f'<span class="{cls}">[{status}] {field}: {detail}</span>')
            checks_html = f'<div class="checks">{" ".join(check_items)}</div>'

        html_parts.append(f'''
<div class="stmt">
<div class="hdr {color_class}">
  <span>{cn_name}</span>
  <span class="info">报告期: {period_label} | 字段数: {len(all_fields)}项</span>
</div>
<div class="table-wrap">
<table>
<thead><tr><th style="width:350px">字段名称</th><th>数值（元）</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>{checks_html}</div>''')

    html_parts.append(f'''<div class="footer">
  数据来源: 东方财富数据中心 | 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}
</div>
</div>
</body>
</html>''')

    html = "\n".join(html_parts)
    out_path = os.path.join(out_dir, "report.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
