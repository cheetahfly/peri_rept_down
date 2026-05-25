# -*- coding: utf-8 -*-
"""
探索东方财富API返回的数据结构 - 查看所有列和数据类型
"""
import requests, json

BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}

REPORTS = {
    "RPT_DMSK_FN_INCOME": "利润表",
    "RPT_DMSK_FN_BALANCE": "资产负债表",
    "RPT_DMSK_FN_CASHFLOW": "现金流量表",
}

for report_name, report_cn in REPORTS.items():
    print(f"\n{'='*70}")
    print(f"{report_cn} ({report_name})")
    print(f"{'='*70}")

    params = {
        "reportName": report_name,
        "columns": "ALL",
        "filter": '(SECURITY_CODE="002475")',
        "pageNumber": 1,
        "pageSize": 20,
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
    }
    r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
    data = r.json()

    if not data.get("success"):
        print(f"  失败: {data.get('message', '')}")
        continue

    items = data.get("result", {}).get("data", [])
    print(f"  数据条数: {len(items)}")

    if not items:
        continue

    # 显示所有列名
    cols = list(items[0].keys())
    print(f"  列数: {len(cols)}")
    print(f"  所有列: {cols}")

    # 显示每条数据的REPORT_DATE, DATE_TYPE_CODE, SECURITY_CODE, UPDATE_DATE
    print(f"\n  各条记录:")
    for item in items:
        print(f"    REPORT_DATE={item.get('REPORT_DATE','')}, "
              f"DATE_TYPE_CODE={item.get('DATE_TYPE_CODE','')}, "
              f"UPDATE_DATE={item.get('UPDATE_DATE','')}, "
              f"SECURITY_CODE={item.get('SECURITY_CODE','')}, "
              f"SECURITY_NAME_ABBR={item.get('SECURITY_NAME_ABBR','')}, "
              f"STD_REPORT_DATE={item.get('STD_REPORT_DATE','')}")
        # For annual reports, show key values
        if str(item.get('DATE_TYPE_CODE','')) == '001' and '2025' in str(item.get('REPORT_DATE','')):
            print(f"    *** 2025年报数据 ***")
            # Print first 10 non-null values
            printed = 0
            for k, v in item.items():
                if v is not None and printed < 15:
                    print(f"      {k} = {v}")
                    printed += 1
