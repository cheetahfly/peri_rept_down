# -*- coding: utf-8 -*-
"""
Tri-channel CF 比对器：tushare vs RDS 逐项对比 + HTML 报告。

用法：
  python scripts/tri_channel_cf_download.py --stock 600519 --year 2020
  python scripts/tri_channel_cf_download.py --stocks-file stocks.txt --year 2022
  TUSHARE_TOKEN=xxx python scripts/tri_channel_cf_download.py --stock 600519 --year 2020
"""
import argparse
import os
import sys
import warnings
from typing import Dict, List

warnings.filterwarnings("ignore")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from astock_fundamentals.sources.api import TushareProvider  # noqa: E402
from astock_fundamentals.sources.rds.rds_loader import RdsLoader  # noqa: E402
from tri_channel_cf_lib import extract_tushare_year_values, tri_match  # noqa: E402

OUT_DIR = "data/exports_v2/cash_flow_tri_channel"
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
os.makedirs(OUT_DIR, exist_ok=True)


def resolve_token(args_token: str = "") -> str:
    """token 解析优先级：--token > TUSHARE_TOKEN env > 错误退出"""
    if args_token:
        return args_token
    env_token = os.environ.get("TUSHARE_TOKEN", "")
    if env_token:
        return env_token
    sys.exit("ERROR: Tushare token required. Pass --token or set TUSHARE_TOKEN env.")


def load_rds_standard(stock_code: str, year: int) -> Dict[str, float]:
    """用 RdsLoader 加载 3 张报表的 annual 数据，返回带表名前缀的 dict"""
    loader = RdsLoader(RDS_DIR)
    out: Dict[str, float] = {}
    for stmt_type in ["balance_sheet", "income_statement", "cash_flow"]:
        try:
            tidy = loader.load_stock_data_tidy(stock_code, year, stmt_type)
        except Exception:
            continue
        for r in tidy:
            if r.get("report_type") != "annual":
                continue
            v = r.get("value")
            if v is None:
                continue
            name = r.get("item_name", "")
            if name:
                out[f"[{stmt_type}] {name}"] = float(v)
    return out


def build_merged_csv(stock: str, year: int, rows: List[Dict], out_path: str) -> None:
    """合并表：每行一个 RDS 项 + 对应 tushare 匹配 + class"""
    import pandas as pd
    df = pd.DataFrame(rows)
    df.insert(0, "stock_code", stock)
    df.insert(1, "report_year", year)
    df.insert(2, "source", "tushare_vs_rds")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")


def build_report_html(stock: str, year: int, rows: List[Dict],
                      tushare_values: Dict[str, float], out_path: str) -> None:
    """生成 HTML 报告，含双层警告横幅 + 彩色对比表"""
    color_css = {
        "exact": "#c8eac8", "sub_yuan": "#f4e4b4", "rounded": "#ffe0a3",
        "large_error": "#f5c2c2", "no_match": "#e8e8e8",
    }
    body = []
    for r in rows:
        bg = color_css.get(r["class"], "#fff")
        rds_v = f"{r['rds_value']:,.2f}" if r['rds_value'] is not None else ""
        ts_v = f"{r['tushare_value']:,.2f}" if r['tushare_value'] is not None else ""
        diff = f"{r['abs_diff']:,.2f}" if r['abs_diff'] is not None else ""
        rel = f"{r['rel_err_pct']:.4f}%" if r['rel_err_pct'] is not None else ""
        body.append(
            f'<tr style="background:{bg}">'
            f'<td>{r["rds_name"]}</td><td class="num">{rds_v}</td>'
            f'<td>{r["tushare_label"] or ""}</td><td class="num">{ts_v}</td>'
            f'<td class="num">{diff}</td><td class="num">{rel}</td>'
            f'<td>{r["class"]}</td></tr>'
        )
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    summary_line = " · ".join(f"{k}={v}" for k, v in counts.items())

    warning_banner1 = """<div class="summary" style="border-left-color:#d73a49;background:#ffe0e0;">
<strong>⚠ 警告 1：</strong>即使 tushare 与 RDS exact_rate 很高，两者可能是同一上游（巨潮资讯）的两次提取。
差异通常源于字段命名 / 精度（rounded 类）。
</div>"""
    warning_banner2 = f"""<div class="summary" style="border-left-color:#0366d6;background:#e3f2fd;">
<strong>ℹ 警告 2：</strong>tushare 标榜源头=巨潮资讯（与 RDS 同源）。本次对比共 {sum(counts.values())} 项；
如果 exact 占比 < 50%，假设"同源"不成立，tushare 可能是第三方转载。
</div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{stock} {year} tushare vs RDS</title>
<style>
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; padding: 20px; }}
h1 {{ color: #1a1a2e; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ padding: 6px 10px; border: 1px solid #e1e4e8; }}
th {{ background: #1a1a2e; color: #fff; }}
.num {{ text-align: right; font-family: Consolas, monospace; }}
.summary {{ padding: 12px; border-left: 4px solid; margin: 12px 0; }}
</style></head><body>
<h1>{stock} - {year} tushare vs RDS 逐项对比</h1>
{warning_banner1}
{warning_banner2}
<div class="summary" style="background:#fff8db;border-left-color:#f0ad4e;">
<strong>项目分布：</strong> {summary_line}<br>
<strong>tushare 字段总数：</strong> {len(tushare_values)}
</div>
<table>
<thead><tr><th>RDS 项目</th><th>RDS 值</th><th>tushare 匹配字段</th><th>tushare 值</th>
<th>差异(元)</th><th>相对误差</th><th>类别</th></tr></thead>
<tbody>{"".join(body)}</tbody>
</table>
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def process_stock(stock: str, year: int, token: str) -> Dict:
    """单只股票 × 单年处理：拉 tushare + RDS + 比对 + 输出报告"""
    try:
        provider = TushareProvider(token=token)
    except Exception as e:
        return {"stock": stock, "year": year, "status": "TOKEN_ERROR", "error": str(e)}

    try:
        tushare_values = extract_tushare_year_values(provider, stock, year)
    except Exception as e:
        return {"stock": stock, "year": year, "status": "EXCEPTION", "error": str(e)}

    if not tushare_values:
        return {"stock": stock, "year": year, "status": "NO_TUSHARE_DATA"}

    rds_standard = load_rds_standard(stock, year)
    if not rds_standard:
        return {"stock": stock, "year": year, "status": "NO_RDS_DATA",
                "tushare_field_count": len(tushare_values)}

    rows = tri_match(tushare_values, rds_standard)

    merged_csv = os.path.join(OUT_DIR, f"{stock}_{year}_tushare vs_rds.csv")
    report_html = os.path.join(OUT_DIR, f"{stock}_{year}_tushare vs_rds.html")
    build_merged_csv(stock, year, rows, merged_csv)
    build_report_html(stock, year, rows, tushare_values, report_html)

    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    return {
        "stock": stock, "year": year, "status": "OK",
        "counts": counts, "merged_csv": merged_csv, "report_html": report_html,
    }


def main():
    import json
    import time

    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", help="single stock code, e.g. 600519")
    ap.add_argument("--stocks-file", help="text file with one stock code per line")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--token", default="", help="Tushare token (overrides env)")
    args = ap.parse_args()

    token = resolve_token(args.token)
    print(f"Token resolved, length: {len(token)}")

    if args.stock:
        stocks = [args.stock]
    elif args.stocks_file:
        with open(args.stocks_file) as f:
            stocks = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    else:
        sys.exit("ERROR: --stock or --stocks-file required")

    results = []
    for code in stocks:
        r = process_stock(code, args.year, token)
        results.append(r)
        print(f"  [{code}] {r['status']}: {r.get('counts', r.get('error', ''))}")
        time.sleep(0.5)

    out = os.path.join(OUT_DIR, f"_run_summary_{args.year}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSummary: {out}")


if __name__ == "__main__":
    main()