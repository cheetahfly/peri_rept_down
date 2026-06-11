# -*- coding: utf-8 -*-
"""
双渠道现金流量表下载 + 比对器。

用法：
  python scripts/dual_channel_cf_download.py --stock 600519 --year 2020
  python scripts/dual_channel_cf_download.py --stocks-file stocks.txt --year 2022

输出：
  data/exports_v2/cash_flow_dual_channel/{stock}_{year}_raw_em.csv
  data/exports_v2/cash_flow_dual_channel/{stock}_{year}_raw_ths.csv
  data/exports_v2/cash_flow_dual_channel/{stock}_{year}_merged.csv  # 双渠道合并 + class 标记
  data/exports_v2/cash_flow_dual_channel/{stock}_{year}_report.html # 高亮报告
"""
import argparse
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import akshare as ak  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dual_channel_cf_lib import (  # noqa: E402
    extract_em_year_values,
    extract_ths_new_year_values,
    dual_match,
)

import pandas as pd  # noqa: E402

OUT_DIR = "data/exports_v2/cash_flow_dual_channel"
os.makedirs(OUT_DIR, exist_ok=True)

FINANCIAL_CODES_YAML = "rules/financial_stock_codes.yaml"


def load_financial_codes():
    """加载金融股代码白名单（banks/insurance/securities 三大类合并去重）"""
    if not os.path.exists(FINANCIAL_CODES_YAML):
        return set()
    with open(FINANCIAL_CODES_YAML, encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}
    s = set()
    for v in d.values():
        if isinstance(v, list):
            s.update(str(c) for c in v)
    return s


FINANCIAL_CODES = load_financial_codes()


def is_financial(code: str) -> bool:
    return code in FINANCIAL_CODES


def em_symbol(code: str) -> str:
    """600/601/603/605/688 → SH; 000/001/002/003/300/301 → SZ; 4/8/9 → BJ"""
    if code.startswith(("600", "601", "603", "605", "688")):
        return "SH" + code
    if code.startswith(("000", "001", "002", "003", "300", "301")):
        return "SZ" + code
    if code.startswith(("4", "8", "92")):
        return "BJ" + code
    raise ValueError(f"Unknown market for {code}")


def download_one(stock: str, year: int):
    """返回 (em_csv_path, ths_csv_path) 或抛异常"""
    em_sym = em_symbol(stock)
    em_csv = os.path.join(OUT_DIR, f"{stock}_{year}_raw_em.csv")
    ths_csv = os.path.join(OUT_DIR, f"{stock}_{year}_raw_ths.csv")

    df_em = ak.stock_cash_flow_sheet_by_yearly_em(symbol=em_sym)
    df_em.to_csv(em_csv, index=False, encoding="utf-8-sig")

    df_ths = ak.stock_financial_cash_new_ths(symbol=stock, indicator="按年度")
    df_ths.to_csv(ths_csv, index=False, encoding="utf-8-sig")

    return em_csv, ths_csv


def build_merged_csv(stock, year, rows, out_path):
    """合并表：每行一个 EM 字段 + 对应 THS 匹配 + class"""
    df = pd.DataFrame(rows)
    df.insert(0, "stock_code", stock)
    df.insert(1, "report_year", year)
    df.insert(2, "source", "em_yearly+ths_new_yearly")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")


def build_report_html(stock, year, rows, out_path, is_fin=False):
    color_css = {
        "exact": "#c8eac8", "sub_yuan": "#f4e4b4", "rounded": "#ffe0a3",
        "large_error": "#f5c2c2", "no_match": "#e8e8e8",
    }
    body = []
    for r in rows:
        bg = color_css.get(r["class"], "#fff")
        em_v = f"{r['em_value']:,.2f}" if r['em_value'] is not None else ""
        ths_v = f"{r['ths_value']:,.2f}" if r['ths_value'] is not None else ""
        diff = f"{r['abs_diff']:,.2f}" if r['abs_diff'] is not None else ""
        rel = f"{r['rel_err_pct']:.4f}%" if r['rel_err_pct'] is not None else ""
        body.append(
            f'<tr style="background:{bg}">'
            f'<td>{r["em_field"]}</td><td class="num">{em_v}</td>'
            f'<td>{r["ths_label"] or ""}</td><td class="num">{ths_v}</td>'
            f'<td class="num">{diff}</td><td class="num">{rel}</td>'
            f'<td>{r["class"]}</td></tr>'
        )
    counts = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    summary_line = " · ".join(f"{k}={v}" for k, v in counts.items())

    # 跨渠道一致性警告横幅（300750 案例反例）
    warning_banner = """<div class="summary" style="border-left-color:#d73a49;background:#ffe0e0;">
<strong>⚠ 重要警告</strong>：本报告仅展示 EM 与 THS 新版的相互一致性。<br>
当两个渠道都集体降级精度时（如 300750 案例 EM/THS 都降到百元精度），所有项目都会显示 "exact" 但实际数值与真实财报有差异。<br>
<strong>2022+ 数据务必用 PDF 年报抽样校验</strong>（参考 Job 1 baseline: docs/audit/2026-06-12-pdf-extraction-baseline.md）。
</div>"""

    # 金融股提示横幅
    fin_banner = ""
    if is_fin:
        fin_banner = """<div class="summary" style="border-left-color:#0366d6;background:#e3f2fd;">
<strong>💼 金融股提示</strong>：该股票为金融股（银行/保险/券商），其 CF schema 与普通股不同（316列 vs 254列）。<br>
RDS 标准数据应使用 cf_f.rds（非 cf_o.rds）。EM 部分字段名为通用名（如 OTHER_ASSET_IMPAIRMENT 实际存"客户存款"值），需查 <code>rules/cf_field_map_financial.yaml</code> 解读。
</div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{stock} {year} CF EM vs THS new</title>
<style>
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; padding: 20px; }}
h1 {{ color: #1a1a2e; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ padding: 6px 10px; border: 1px solid #e1e4e8; }}
th {{ background: #1a1a2e; color: #fff; }}
.num {{ text-align: right; font-family: Consolas, monospace; }}
.summary {{ background: #fff8db; padding: 12px; border-left: 4px solid #f0ad4e; margin: 12px 0; }}
code {{ background:#f5f5f5; padding:1px 4px; border-radius:3px; }}
</style></head><body>
<h1>{stock} - {year} 年报现金流量表 EM vs THS新版 双渠道对比</h1>
{warning_banner}
{fin_banner}
<div class="summary"><strong>项目分布：</strong> {summary_line}</div>
<table>
<thead><tr><th>EM 字段</th><th>EM 值</th><th>THS 匹配字段</th><th>THS 值</th>
<th>差异(元)</th><th>相对误差</th><th>类别</th></tr></thead>
<tbody>{"".join(body)}</tbody>
</table>
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def process_stock(stock: str, year: int):
    is_fin = is_financial(stock)
    label = " (金融股)" if is_fin else ""
    print(f"\n[{stock} {year}]{label} downloading...")
    try:
        em_csv, ths_csv = download_one(stock, year)
    except Exception as e:
        print(f"  [ERROR] download: {type(e).__name__}: {e}")
        return {"stock": stock, "year": year, "status": "DOWNLOAD_FAILED",
                "error": str(e), "is_financial": is_fin}

    em_v = extract_em_year_values(em_csv, year)
    ths_v = extract_ths_new_year_values(ths_csv, year)
    if not em_v:
        return {"stock": stock, "year": year, "status": "NO_EM_DATA", "is_financial": is_fin}
    if not ths_v:
        return {"stock": stock, "year": year, "status": "NO_THS_DATA", "is_financial": is_fin}

    rows = dual_match(em_v, ths_v)
    merged_csv = os.path.join(OUT_DIR, f"{stock}_{year}_merged.csv")
    report_html = os.path.join(OUT_DIR, f"{stock}_{year}_report.html")
    build_merged_csv(stock, year, rows, merged_csv)
    build_report_html(stock, year, rows, report_html, is_fin=is_fin)

    counts = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    print(f"  [OK] em={len(em_v)} ths={len(ths_v)}  分布: {counts}")
    return {"stock": stock, "year": year, "status": "OK", "counts": counts,
            "merged_csv": merged_csv, "report_html": report_html,
            "is_financial": is_fin}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", help="single stock code, e.g. 600519")
    ap.add_argument("--stocks-file", help="text file with one stock code per line")
    ap.add_argument("--year", type=int, required=True, help="report year, e.g. 2022")
    args = ap.parse_args()

    if args.stock:
        stocks = [args.stock]
    elif args.stocks_file:
        with open(args.stocks_file) as f:
            stocks = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    else:
        ap.error("--stock or --stocks-file required")

    results = []
    for code in stocks:
        results.append(process_stock(code, args.year))
        time.sleep(0.5)

    out = os.path.join(OUT_DIR, f"_run_summary_{args.year}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSummary: {out}")


if __name__ == "__main__":
    main()
