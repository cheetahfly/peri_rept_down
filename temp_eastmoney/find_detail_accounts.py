# -*- coding: utf-8 -*-
"""
探索东方财富API的详细财务报表附注数据
年报附注中包含几百项明细数据
"""
import requests

BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}

# 报表附注明细类API
CANDIDATES = [
    # 货币资金明细
    ("RPT_DMSK_FN_MONETARYFUNDS", "货币资金明细"),
    # 应收账款明细
    ("RPT_DMSK_FN_ACCOUNTS_RECE", "应收账款明细"),
    # 存货明细
    ("RPT_DMSK_FN_INVENTORY_DETAIL", "存货明细"),
    # 固定资产明细
    ("RPT_DMSK_FN_FIXED_ASSET", "固定资产明细"),
    # 短期借款明细
    ("RPT_DMSK_FN_SHORT_LOAN", "短期借款"),
    # 长期借款明细
    ("RPT_DMSK_FN_LONG_LOAN", "长期借款"),
    # 营业收入明细
    ("RPT_DMSK_FN_INCOME_DETAIL", "收入明细"),
    # 营业成本明细
    ("RPT_DMSK_FN_COST_DETAIL", "成本明细"),
    # 费用明细
    ("RPT_DMSK_FN_EXPENSE_DETAIL", "费用明细"),

    # 全面财务报告 - 可能包含所有明细
    ("RPT_DMSK_FN_FULL_REPORT", "完整财务报告"),
    ("RPT_FN_FINANCE_MAIN_INDICATOR", "主要指标"),
    ("RPT_DMSK_FN_FINANCE_DATA", "财务数据"),

    # 资产负债表完整版
    ("RPT_DMSK_FN_BS_FULL", "资产负债表完整"),
    ("RPT_FN_BS_DETAIL", "资产负债表明细"),
    ("RPT_DMSK_FN_BALANCE_SHEET_FULL", "资产负债表完整2"),

    # 利润表完整版
    ("RPT_DMSK_FN_IS_FULL", "利润表完整"),
    ("RPT_FN_IS_DETAIL", "利润表明细"),

    # 现金流量表完整版
    ("RPT_DMSK_FN_CF_FULL", "现金流量表完整"),
    ("RPT_FN_CF_DETAIL", "现金流量表明细"),

    # 附注数据
    ("RPT_DMSK_FN_NOTES", "报表附注"),
    ("RPT_DMSK_FN_ACCOUNTING_ITEMS", "会计科目明细"),
    ("RPT_FN_ACCOUNT_DETAIL", "科目明细"),

    # 各科目余额表
    ("RPT_DMSK_FN_TB", "试算平衡表"),
    ("RPT_DMSK_FN_BS_ITEMS", "资产负债表项目"),
    ("RPT_DMSK_FN_IS_ITEMS", "利润表项目"),
    ("RPT_DMSK_FN_CF_ITEMS", "现金流量表项目"),
]

for name, label in CANDIDATES:
    params = {
        "reportName": name,
        "columns": "ALL",
        "filter": '(SECURITY_CODE="002475")',
        "pageNumber": 1,
        "pageSize": 3,
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
    }
    try:
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=10)
        data = r.json()
        if data.get("success"):
            items = data.get("result", {}).get("data", [])
            if items:
                # Check for 2025 annual
                for item in items:
                    dt = str(item.get("DATE_TYPE_CODE", ""))
                    rd = str(item.get("REPORT_DATE", ""))
                    if dt == "001" and "2025" in rd:
                        cols = list(item.keys())
                        non_null = sum(1 for k in cols if item.get(k) not in (None, ''))
                        print(f"[OK] {name:40s} {label:20s} cols={len(cols)} nn={non_null}")
                        # Show first 10 non-metadata columns
                        shown = 0
                        for k in cols[:30]:
                            if k not in ("SECUCODE","SECURITY_CODE","INDUSTRY_CODE","ORG_CODE","SECURITY_NAME_ABBR","INDUSTRY_NAME","MARKET","SECURITY_TYPE_CODE","TRADE_MARKET_CODE","DATE_TYPE_CODE","REPORT_TYPE_CODE","DATA_STATE","NOTICE_DATE","REPORT_DATE","STD_REPORT_DATE"):
                                print(f"    {k}: {item.get(k)}")
                                shown += 1
                                if shown >= 5: break
                        break
                else:
                    print(f"[--] {name:40s} {label:20s} 有数据但无2025年报")
            else:
                print(f"[--] {name:40s} {label:20s} 无数据")
        else:
            msg = data.get("message", "")
            if "不存在" not in msg:
                print(f"[NO] {name:40s} {label:20s} {msg[:50]}")
    except Exception as e:
        print(f"[ER] {name:40s} {label:20s} {e}")
