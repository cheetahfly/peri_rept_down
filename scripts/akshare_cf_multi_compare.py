# -*- coding: utf-8 -*-
"""
多股多渠道对比 vs RDS 标准。

对每只股票每个渠道：
  - 提取 2020 年报数据
  - 用 best-match 与 RDS 49+ 项对比
  - 分类：exact / sub_yuan / rounded / large_error / no_match
  - 统计精度：是否精确到分（exact 占比）

特别关注：精度因股票而异的假设 — 比较每只股票在 EM/THS new 上的 exact_rate
"""
import os
import sys
import json
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extraction.ground_truth.rds_loader import RdsLoader  # noqa: E402
from akshare_cf_test_compare import (  # noqa: E402
    extract_em_2020_values,
    extract_ths_new_2020_values,
    best_match,
)

OUT_DIR = "tmp/akshare_test_multi_stocks_2020"
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"

STOCKS = [
    ("600887", "伊利股份", "上海主板"),
    ("600036", "招商银行", "上海主板(金融)"),
    ("000651", "格力电器", "深圳主板"),
    ("688981", "中芯国际", "上海科创板"),
    ("300750", "宁德时代", "深圳创业板"),
]

CHANNELS = [
    ("em_yearly",      extract_em_2020_values),
    ("em_report",      extract_em_2020_values),
    ("em_delisted",    extract_em_2020_values),
    ("ths_new_report", extract_ths_new_2020_values),
    ("ths_new_yearly", extract_ths_new_2020_values),
]

INDIRECT_CODES_NON_FINANCIAL = {
    "F044N","F046N","F047N","F048N","F050N","F051N","F053N","F054N",
    "F055N","F056N","F057N","F058N","F060N","F066N","F067N","F071N","F096N"
}


def cls_diff(diff, rel):
    if diff is None:
        return "no_match"
    if diff < 0.01:
        return "exact"
    if diff < 1.0:
        return "sub_yuan"
    if rel < 1.0:
        return "rounded"
    return "large_error"


def main():
    loader = RdsLoader(RDS_DIR)
    matrix = []  # 每行 = (stock, channel, summary)
    all_details = {}

    for code, name, board in STOCKS:
        # RDS 标准
        tidy = loader.load_stock_data_tidy(code, 2020, "cash_flow")
        annual = [r for r in tidy if r["report_type"] == "annual"]
        rds_items = [r for r in annual if r["value"] is not None]
        rds_indirect = sum(1 for r in rds_items if r["item_code"] in INDIRECT_CODES_NON_FINANCIAL)
        rds_n = len(rds_items)
        print(f"\n=== {code} {name} ({board}) ===  RDS 标准: {rds_n} 项 (其中间接法 {rds_indirect} 项)")

        for ch_label, extractor in CHANNELS:
            csv_path = os.path.join(OUT_DIR, f"raw_{code}_{ch_label}.csv")
            if not os.path.exists(csv_path):
                print(f"  [{ch_label}] CSV not found (download failed), skip")
                matrix.append({
                    "stock_code": code, "stock_name": name, "board": board,
                    "channel": ch_label, "status": "DOWNLOAD_FAILED",
                    "channel_fields": 0, "exact": 0, "sub_yuan": 0, "rounded": 0,
                    "large_error": 0, "no_match": 0,
                    "exact_rate": 0.0, "indirect_exact": 0,
                })
                continue
            try:
                ch_values = extractor(csv_path)
            except Exception as e:
                print(f"  [{ch_label}] ERROR extracting: {e}")
                ch_values = {}

            details = []
            counters = {"exact": 0, "sub_yuan": 0, "rounded": 0, "large_error": 0, "no_match": 0}
            indirect_exact = 0
            for item in rds_items:
                rds_v = item["value"]
                if rds_v is None or rds_v == 0:
                    continue
                label, ch_v, diff, rel = best_match(rds_v, ch_values)
                klass = cls_diff(diff, rel)
                counters[klass] += 1
                if klass == "exact" and item["item_code"] in INDIRECT_CODES_NON_FINANCIAL:
                    indirect_exact += 1
                details.append({
                    "rds_item_code": item["item_code"],
                    "rds_item_name": item["item_name"],
                    "rds_value": rds_v,
                    "ch_label": label,
                    "ch_value": ch_v,
                    "abs_diff": diff,
                    "rel_err_pct": rel,
                    "class": klass,
                })

            total = sum(counters.values())
            exact_rate = (counters["exact"] / total * 100) if total else 0.0
            summary = {
                "stock_code": code, "stock_name": name, "board": board,
                "channel": ch_label, "status": "OK",
                "channel_fields": len(ch_values),
                **counters,
                "exact_rate": round(exact_rate, 2),
                "indirect_exact_count": indirect_exact,
                "indirect_total_rds": rds_indirect,
            }
            matrix.append(summary)
            all_details[f"{code}_{ch_label}"] = details
            print(f"  [{ch_label:18s}] fields={len(ch_values):3d}  exact={counters['exact']:3d}/{total:3d} ({exact_rate:5.1f}%)  "
                  f"rounded={counters['rounded']:2d}  large={counters['large_error']:2d}  "
                  f"间接法精确={indirect_exact}/{rds_indirect}")

    # 保存详细 JSON
    out_path = os.path.join(OUT_DIR, "_compare_matrix.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "matrix": matrix,
            "details": all_details,
            "stocks": STOCKS,
            "channels": [c[0] for c in CHANNELS],
        }, f, ensure_ascii=False, indent=2)

    # 精度稳定性矩阵
    print("\n" + "="*100)
    print("精度稳定性矩阵（每个单元格 = exact 占 RDS 项目数 的百分比）")
    print("="*100)
    header = f"{'stock':30s}"
    for c in CHANNELS:
        header += f" {c[0]:>16s}"
    print(header)
    for code, name, board in STOCKS:
        row = f"{code} {name} ({board[:8]:>8s})"
        row = f"{row:30s}"
        for ch_label, _ in CHANNELS:
            cell = next((m for m in matrix if m["stock_code"]==code and m["channel"]==ch_label), None)
            if cell is None or cell["status"]!="OK":
                row += f" {'FAIL':>16s}"
            else:
                row += f" {cell['exact_rate']:>15.1f}%"
        print(row)
    print(f"\n详细矩阵: {out_path}")


if __name__ == "__main__":
    main()
