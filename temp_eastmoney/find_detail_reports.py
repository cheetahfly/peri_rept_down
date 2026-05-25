# -*- coding: utf-8 -*-
"""
寻找东方财富API中更详细的财务报表端点
"""
import requests

BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}

# 更多候选的reportName - 包含明细数据的报表
CANDIDATES = [
    # 已有的总括报表
    ("RPT_DMSK_FN_INCOME", "利润表(已用)"),
    ("RPT_DMSK_FN_BALANCE", "资产负债表(已用)"),
    ("RPT_DMSK_FN_CASHFLOW", "现金流量表(已用)"),

    # 可能更详细的版本
    ("RPT_DMSK_FN_INCOME_DETAIL", "利润表明细"),
    ("RPT_DMSK_FN_BALANCE_DETAIL", "资产负债表明细"),
    ("RPT_DMSK_FN_CASHFLOW_DETAIL", "现金流量表明细"),

    # 其他可能
    ("RPT_DMSK_FN_INCOME_NEW", "利润表新"),
    ("RPT_DMSK_FN_BALANCE_NEW", "资产负债表新"),
    ("RPT_DMSK_FN_CASHFLOW_NEW", "现金流量表新(已有)"),

    # 按会计准则分类
    ("RPT_FN_FINANCE_INCOME", "财务利润表"),
    ("RPT_FN_FINANCE_BALANCE", "财务资产负债表"),
    ("RPT_FN_FINANCE_CASHFLOW", "财务现金流量表"),

    # 母公司报表
    ("RPT_DMSK_FN_INCOME_PARENT", "利润表(母公司)"),
    ("RPT_DMSK_FN_BALANCE_PARENT", "资产负债表(母公司)"),
    ("RPT_DMSK_FN_CASHFLOW_PARENT", "现金流量表(母公司)"),

    # 可能包含所有科目的详细报表
    ("RPT_DMSK_FN_ALLFIN_DATA", "全部财务数据"),
    ("RPT_DMSK_FN_FINANCE_MAIN", "主要财务指标"),
    ("RPT_FN_FINANCE", "财务数据"),
    ("RPT_FN_FINANCE_DETAIL", "财务明细"),
]

def explore_report(report_name, label):
    params = {
        "reportName": report_name,
        "columns": "ALL",
        "filter": '(SECURITY_CODE="002475")',
        "pageNumber": 1,
        "pageSize": 5,
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
    }
    try:
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        data = r.json()
        if data.get("success"):
            items = data.get("result", {}).get("data", [])
            if items:
                # Find 2025 annual
                for item in items:
                    dt = str(item.get("DATE_TYPE_CODE", ""))
                    rd = str(item.get("REPORT_DATE", ""))
                    if dt == "001" and "2025" in rd:
                        cols = list(item.keys())
                        non_null = sum(1 for k in cols if item.get(k) is not None)
                        print(f"[OK] {report_name:40s} {label:20s} 总列数={len(cols):3d} 非空列={non_null:2d}")
                        return True
                # No 2025 annual but has data
                cols = list(items[0].keys())
                print(f"[--] {report_name:40s} {label:20s} 有数据但无2025年报, 列数={len(cols)}")
                return False
            else:
                print(f"[XX] {report_name:40s} {label:20s} 无数据")
                return False
        else:
            print(f"[NO] {report_name:40s} {label:20s} {data.get('message','')}")
            return False
    except Exception as e:
        print(f"[ER] {report_name:40s} {label:20s} {e}")
        return False

print("=" * 70)
print("探索东方财富API详细财务报表端点")
print("=" * 70)

for name, label in CANDIDATES:
    explore_report(name, label)
