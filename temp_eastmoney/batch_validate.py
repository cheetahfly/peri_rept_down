# -*- coding: utf-8 -*-
"""
批量数据复核 - 跨期跨公司一致性验证
支持：会计恒等式检查、累计口径验证、跨期趋势检查
"""
import os, sys, json

BASE = os.path.dirname(os.path.abspath(__file__))
BATCH_DIR = os.path.join(BASE, "batch_data")

# 股票名称映射
STOCK_NAMES = {
    "000001": "平安银行", "000333": "美的集团", "000858": "五粮液",
    "002415": "海康威视", "002475": "立讯精密", "300750": "宁德时代",
    "600036": "招商银行", "600519": "贵州茅台", "600887": "伊利股份",
    "601318": "中国平安",
}

PERIOD_ORDER = {"一季报": 1, "半年报": 2, "三季报": 3, "年报": 4}


def load_summary(code, year, period):
    """加载单条摘要"""
    path = os.path.join(BATCH_DIR, code, f"{year}_{period}", "summary.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def safe_float(val):
    if val is None: return None
    try: return float(val)
    except: return None


def verify_accounting_equation(data, label):
    """验证会计恒等式: 资产 = 负债 + 所有者权益"""
    bs = data.get("balance_sheet", {})
    kf = bs.get("key_fields", {}) if bs else {}
    assets = safe_float(kf.get("资产总计"))
    liab = safe_float(kf.get("负债合计"))
    equity = safe_float(kf.get("所有者权益合计"))
    if all(x is not None for x in [assets, liab, equity]):
        diff = abs(assets - liab - equity)
        ratio = diff / assets if assets else 0
        if ratio < 0.005:
            return (f"  [OK] {label}: {assets/1e8:.2f}亿 = {liab/1e8:.2f}亿 + {equity/1e8:.2f}亿", True)
        else:
            return (f"  [!] {label}: 偏差 {diff/1e8:.4f}亿 (ratio={ratio*100:.4f}%)", False)
    return (f"  [-] {label}: 数据不完整", None)


def verify_cumulative_trend(code, year):
    """验证同一年内累计口径: Q1 ≤ H1 ≤ Q3 ≤ Annual"""
    periods = ["一季报", "半年报", "三季报", "年报"]
    issues = []
    # 只对利润表做累计口径检查(资产负债表无累计概念)
    metrics = [
        ("利润表", "income_statement", "营业收入"),
        ("利润表", "income_statement", "归母净利润"),
    ]

    for stmt_cn, en, metric in metrics:
        vals = []
        for p in periods:
            data = load_summary(code, year, p)
            if not data or en not in data or not data[en]:
                continue
            v = safe_float(data[en].get("key_fields", {}).get(metric))
            if v is not None:
                vals.append((p, v))
        if len(vals) >= 2:
            for i in range(len(vals) - 1):
                if vals[i][1] > vals[i + 1][1]:
                    issues.append(
                        f"  [!] {year}年{metric}: {vals[i][0]}({vals[i][1]/1e8:.2f}亿) > "
                        f"{vals[i+1][0]}({vals[i+1][1]/1e8:.2f}亿)")

    return issues


def main():
    print("=" * 70)
    print("  批量数据复核验证")
    print("=" * 70)

    all_issues = []
    passed = 0
    failed = 0
    missing = 0

    for code, name in sorted(STOCK_NAMES.items()):
        print(f"\n--- {code} {name} ---")
        code_dir = os.path.join(BATCH_DIR, code)
        if not os.path.isdir(code_dir):
            print(f"  [缺失] 无数据")
            continue

        # 收集所有可用期间
        periods_found = set()
        for d in os.listdir(code_dir):
            if "_" in d and os.path.isdir(os.path.join(code_dir, d)):
                try:
                    y, p = d.split("_", 1)
                    periods_found.add((int(y), p))
                except: pass

        # 会计恒等式验证
        eq_ok = 0
        eq_total = 0
        for y, p in sorted(periods_found):
            data = load_summary(code, y, p)
            if not data:
                continue
            label = f"{y}年{p}"
            msg, ok = verify_accounting_equation(data, label)
            print(msg)
            if ok is True:
                eq_ok += 1
                eq_total += 1
            elif ok is False:
                eq_total += 1
                all_issues.append(msg)
            # ok is None = incomplete data

        if eq_total > 0:
            print(f"  会计恒等式: {eq_ok}/{eq_total} 通过")

        # 累计口径验证
        years = sorted(set(y for y, p in periods_found))
        for y in years:
            issues = verify_cumulative_trend(code, y)
            for issue in issues:
                print(issue)
                all_issues.append(issue)

    # 总结
    print(f"\n{'='*70}")
    print(f"  验证总结")
    print(f"{'='*70}")
    if all_issues:
        print(f"  发现 {len(all_issues)} 个问题:")
        for issue in all_issues:
            print(f"  {issue}")
    else:
        print(f"  所有检查通过!")
    print(f"\n  覆盖: {len(STOCK_NAMES)} 只股票")


if __name__ == "__main__":
    main()
