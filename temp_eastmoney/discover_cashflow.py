# -*- coding: utf-8 -*-
"""
探索东方财富API中现金流量表的正确reportName
"""
import requests
import json

BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}

# 候选的现金流量表reportName
CANDIDATES = [
    "RPT_DMSK_FN_CASHFLOW",       # 已试过，无数据
    "RPT_DMSK_FN_CASH_FLOW",
    "RPT_FN_CASHFLOW",
    "RPT_FN_CASH_FLOW",
    "RPT_FN_FINANCE_CASHFLOW",
    "RPT_DMSK_FN_CASHFLOW_NEW",
    "RPT_DMSK_FN_CASHFLOW_ALL",
    "RPT_FN_CF",                   # Cash Flow简写
    "RPT_FN_ACC_CASHFLOW",
    "RPT_FN_CASHFLOW_STANDARD",
    "RPT_FN_CASHFLOW_PARENT",
    "RPT_DMSK_FN_CF",
    # 一些其他可能的名字
    "RPT_FN_LR",                   # 利润表
    "RPT_FN_ZCFZB",                # 资产负债表
    "RPT_FN_XJLLB",                # 现金流量表拼音首字母
]

def test_report(report_name):
    params = {
        "reportName": report_name,
        "columns": "ALL",
        "filter": '(SECURITY_CODE="002475")',
        "pageNumber": 1,
        "pageSize": 10,
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
    }
    try:
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        data = r.json()
        if data.get("success"):
            items = data.get("result", {}).get("data", [])
            if items:
                print(f"  [OK] {report_name}: {len(items)} 条数据")
                cols = list(items[0].keys())
                # 显示关键列
                interesting = [c for c in cols if any(k in c.upper() for k in
                    ["CASH", "FLOW", "RECEIV", "PAY", "NET", "OPERAT", "INVEST", "FINANC",
                     "DEPRECI", "AMORT", "PROCEED", "PURCHASE", "DIVIDEND", "INTEREST"])]
                print(f"     关键列: {interesting[:20]}")
                print(f"     所有列数: {len(cols)}")
                # 显示第一条的部分数据
                first = items[0]
                for k in interesting[:10]:
                    print(f"       {k} = {first.get(k, 'N/A')}")
                return True
            else:
                print(f"  [--] {report_name}: 成功但无数据")
        else:
            msg = data.get("message", "未知错误")
            print(f"  [NO] {report_name}: {msg}")
    except Exception as e:
        print(f"  [NO] {report_name}: 异常 - {e}")
    return False

print("=" * 60)
print("探索东方财富API现金流量表reportName")
print("=" * 60)

# 先验证已知可用的作为基准
print("\n【基准测试】已知可用的报表:")
test_report("RPT_DMSK_FN_INCOME")
test_report("RPT_DMSK_FN_BALANCE")

print("\n【探索】候选现金流量表名称:")
found = []
for name in CANDIDATES:
    if test_report(name):
        found.append(name)

if found:
    print(f"\n[OK] 找到现金流量表: {found}")
else:
    print("\n[NO] 所有候选名称均未找到现金流量表")
    print("\n尝试搜索API可用的所有reportName...")
