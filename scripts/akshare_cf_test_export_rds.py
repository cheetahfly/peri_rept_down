# -*- coding: utf-8 -*-
"""导出 600519 2020 年报现金流量表 RDS 标准数据到 JSON。"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extraction.ground_truth.rds_loader import RdsLoader

OUT_DIR = "tmp/akshare_test_600519_2020"
os.makedirs(OUT_DIR, exist_ok=True)

loader = RdsLoader("D:/Research/Quant/SETL/cninfo/data_backup")
tidy = loader.load_stock_data_tidy("600519", 2020, "cash_flow")
annual = [r for r in tidy if r["report_type"] == "annual"]

records = []
for r in annual:
    records.append({
        "item_code": r["item_code"],
        "item_name": r["item_name"],
        "value": float(r["value"]) if r["value"] is not None else None,
        "display_order": r.get("display_order", 0),
    })

out_path = os.path.join(OUT_DIR, "rds_standard_600519_2020_cf.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({
        "stock_code": "600519",
        "report_year": 2020,
        "report_type": "annual",
        "statement_type": "cash_flow",
        "source": "RDS (cninfo/data_backup/cf_o.rds)",
        "item_count": len(records),
        "items": records,
    }, f, ensure_ascii=False, indent=2)

print(f"已导出 RDS 标准数据：{out_path}")
print(f"条目数：{len(records)}")
