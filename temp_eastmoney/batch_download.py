# -*- coding: utf-8 -*-
"""
批量下载多只股票的多期财报数据 - 支持断点续传
数据保存: batch_data/{stock_code}/{year}_{period_short}/
  period_short: 年报/半年报/一季报/三季报  (使用英文前缀避免编码问题)
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em_common import *

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_data")

# 股票列表 (code, name, exchange)  sz=深圳, sh=上海
STOCKS = [
    ("002475", "立讯精密", "sz"),
    ("000333", "美的集团", "sz"),
    ("600519", "贵州茅台", "sh"),
    ("000858", "五粮液", "sz"),
    ("601318", "中国平安", "sh"),
    ("600036", "招商银行", "sh"),
    ("000001", "平安银行", "sz"),
    ("600887", "伊利股份", "sh"),
    ("002415", "海康威视", "sz"),
    ("300750", "宁德时代", "sz"),
]

# 报告期定义
PERIODS = [
    ("001", "年报",    "{y}-12-31", "年报"),
    ("002", "半年报",  "{y}-06-30", "半年报"),
    ("003", "一季报",  "{y}-03-31", "一季报"),
    ("004", "三季报",  "{y}-09-30", "三季报"),
]

YEARS = list(range(2020, 2026 + 1))

# 进度文件
PROGRESS_FILE = os.path.join(OUT_DIR, "_progress.json")


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"completed": []}


def save_progress(completed):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"completed": completed}, f)


def download_stock_period(code, name, period_code, period_short, report_date, label, save_dir):
    """下载单只股票单个报告期"""
    os.makedirs(save_dir, exist_ok=True)

    summary_path = os.path.join(save_dir, "summary.json")
    if os.path.exists(summary_path):
        return "skipped"

    results = {}
    for en_name in ["income_statement", "balance_sheet", "cash_flow"]:
        item, err = fetch_report(en_name, code, period_code, report_date)
        if err:
            print(f"    {en_name}: {err}")
            results[en_name] = None
            continue

        raw_path = os.path.join(save_dir, f"{en_name}_raw.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2, default=str)
        results[en_name] = item

    if any(v for v in results.values()):
        summary = {}
        for en_name, item in results.items():
            if not item:
                summary[en_name] = None
                continue
            summary[en_name] = {"报表名称": REPORT_DEFS[en_name]["name"]}
            summary[en_name]["key_fields"] = {}
            for cn, field in get_key_fields(en_name).items():
                summary[en_name]["key_fields"][cn] = item.get(field)

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

        try:
            generate_html(results, "三大报表", label, save_dir)
        except Exception as e:
            pass

        return "OK"
    return "无数据"


def main():
    print("=" * 70)
    print("  批量下载A股财报数据 (东方财富API) - 支持断点续传")
    print("=" * 70)

    progress = load_progress()
    completed = set(progress["completed"])

    stats = {"OK": 0, "skipped": 0, "无数据": 0}

    for code, name, exchange in STOCKS:
        print(f"\n{'='*70}")
        print(f"  {code} {name}")
        print(f"{'='*70}")

        for period_code, period_short, date_fmt, _ in PERIODS:
            for y in YEARS:
                report_date = date_fmt.format(y=y)
                label = f"{y}年{period_short}"
                dir_name = f"{y}_{period_short}"
                save_dir = os.path.join(OUT_DIR, code, dir_name)

                task_key = f"{code}/{dir_name}"
                if task_key in completed:
                    stats["skipped"] += 1
                    continue

                status = download_stock_period(code, name, period_code, period_short,
                                               report_date, label, save_dir)
                stats[status] = stats.get(status, 0) + 1

                if status != "skipped":
                    if status == "OK":
                        print(f"  [OK] {label}")
                    else:
                        print(f"  [{status}] {label}")
                    completed.add(task_key)
                    save_progress(list(completed))

                time.sleep(0.2)

    # 总结
    print(f"\n{'='*70}")
    print(f"  下载完成")
    print(f"{'='*70}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print(f"  总计: {sum(stats.values())}")
    print(f"\n  数据目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
