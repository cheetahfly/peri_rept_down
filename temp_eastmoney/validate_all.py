# -*- coding: utf-8 -*-
"""
跨期数据复核 - 对比立讯精密(002475) 各报告期的关键财务数据
支持: 年报/半年报/一季报/三季报 交叉验证
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em_common import *

BASE = os.path.dirname(os.path.abspath(__file__))

# 各报告期定义
PERIODS = [
    ("2026年一季报", "q1_2026", "2026-03-31"),
    ("2025年年报",   "temp_eastmoney", "2025-12-31"),  # 年报特殊: 数据在父目录已有
    ("2025年三季报", "q3_2025", "2025-09-30"),
    ("2025年半年报", "half_year_2025", "2025-06-30"),
    ("2025年一季报", "q1_2025", "2025-03-31"),
]


def load_period_data(label, subdir, report_date):
    """尝试从子项目的summary.json或原始JSON加载数据"""
    # 年报特殊处理: 从父目录的fin JSON加载
    # 注意: 必须排除"半年报"(包含"年报"子串)
    if "年报" in label and "半年报" not in label:
        summary_path = os.path.join(BASE, "luxun_precision_2025_financials.json")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 转换格式以匹配子项目结构
            result = {}
            for en_name, v in data.items():
                result[en_name] = {"key_fields": v.get("key_fields", {})}
            return result
        # 回退: 直接下载
        print(f"  [!] {summary_path} 不存在，尝试直接从API下载年报...")
        return fetch_all(report_date, "001")

    summary_path = os.path.join(BASE, subdir, "summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def fetch_all(report_date_str, date_type_code):
    """直接下载某个报告期的全部数据"""
    result = {}
    for en_name in ["income_statement", "balance_sheet", "cash_flow"]:
        item, err = fetch_report(en_name, "002475", date_type_code, report_date_str)
        if item:
            result[en_name] = {"key_fields": {}}
            for cn, field in get_key_fields(en_name).items():
                result[en_name]["key_fields"][cn] = item.get(field)
    return result if result else None


def compare_key_fields(periods_data):
    """对比所有报告期的关键财务指标"""
    # 收集所有出现的指标名
    all_metrics = set()
    for label, data in periods_data:
        if not data: continue
        for stmt in data.values():
            for k in stmt.get("key_fields", {}):
                all_metrics.add(k)

    # 按报表类型分组
    stmt_order = ["资产负债表", "利润表", "现金流量表"]
    stmt_map = {
        "balance_sheet": "资产负债表",
        "income_statement": "利润表",
        "cash_flow": "现金流量表",
    }
    rev_map = {v: k for k, v in stmt_map.items()}

    output = []
    for stmt_cn in stmt_order:
        en = rev_map.get(stmt_cn)
        output.append(f"\n{'='*80}")
        output.append(f"  {stmt_cn} - 跨期对比")
        output.append(f"{'='*80}")

        # 收集该报表下的指标
        metrics = set()
        for label, data in periods_data:
            if not data or en not in data: continue
            for k in data[en].get("key_fields", {}):
                metrics.add(k)

        for metric in sorted(metrics):
            row = f"  {metric:20s}"
            for label, data in periods_data:
                val = None
                if data and en in data:
                    val = data[en]["key_fields"].get(metric)
                if val is not None:
                    row += f" | {format_value(val):>20s}"
                else:
                    row += f" | {'N/A':>20s}"
            output.append(row)

    return "\n".join(output)


def verify_interperiod(periods_data):
    """跨期勾稽验证"""
    checks = []

    # 按关键指标检查数值趋势合理性
    # 仅检查同一年内(FY2025)的累计口径: Q1 ≤ H1 ≤ Q3 ≤ Annual
    en_map = {"balance_sheet": "资产总计", "income_statement": "营业收入"}

    # 筛选2025年数据并按时间排序: Q1(3月) < H1(6月) < Q3(9月) < 年报(12月)
    fy2025_key = {"2025年一季报", "2025年半年报", "2025年三季报", "2025年年报"}
    fy2025_order = {"2025年一季报": 1, "2025年半年报": 2, "2025年三季报": 3, "2025年年报": 4}

    for en, metric in en_map.items():
        vals = []
        for label, data in periods_data:
            if label not in fy2025_key: continue
            if data and en in data:
                v = data[en]["key_fields"].get(metric)
                if v is not None:
                    vals.append((label, float(v), fy2025_order.get(label, 99)))
        vals.sort(key=lambda x: x[2])  # 按时间排序

        if len(vals) >= 2:
            increasing = all(vals[i][1] <= vals[i+1][1] for i in range(len(vals)-1))
            status = "OK" if increasing else "注意(非单调)"
            checks.append((f"{metric}(2025FY)趋势", status,
                " < ".join(f"{l}:{v/1e8:.1f}亿" for l, v, _ in vals)))

    # 会计恒等式验证 (各期资产负债表)
    for label, data in periods_data:
        if not data or "balance_sheet" not in data: continue
        kf = data["balance_sheet"].get("key_fields", {})
        assets = safe_float(kf.get("资产总计"))
        liab = safe_float(kf.get("负债合计"))
        equity = safe_float(kf.get("所有者权益合计"))
        if all(x is not None for x in [assets, liab, equity]):
            diff = abs(assets - liab - equity)
            if diff / assets < 0.01:
                checks.append((f"{label}恒等式", "OK",
                    f"{assets/1e8:.2f} = {liab/1e8:.2f} + {equity/1e8:.2f}"))
            else:
                checks.append((f"{label}恒等式", "偏差",
                    f"差{diff/1e8:.4f}亿"))

    return checks


def main():
    print("=" * 80)
    print("  立讯精密(002475) 跨期数据复核")
    print("=" * 80)

    periods_data = []
    for label, subdir, rpt_date in PERIODS:
        data = load_period_data(label, subdir, rpt_date)
        status = "OK" if data else "无数据"
        periods_data.append((label, data))
        summary = ""
        if data:
            counts = []
            for en in ["income_statement", "balance_sheet", "cash_flow"]:
                if en in data:
                    n = len(data[en].get("key_fields", {}))
                    counts.append(f"{REPORT_DEFS[en]['name']}({n}项)")
            summary = ", ".join(counts)
        print(f"  [{status}] {label}: {summary}")

    # 跨期对比
    print(compare_key_fields(periods_data))

    # 勾稽验证
    print(f"\n{'='*80}")
    print(f"  数据复核验证")
    print(f"{'='*80}")
    checks = verify_interperiod(periods_data)
    for field, status, detail in checks:
        icon = "OK" if status == "OK" else "!"
        print(f"  [{icon}] {field}: {status}")
        print(f"         {detail}")

    print(f"\n{'='*80}")
    print(f"  复核完成")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
