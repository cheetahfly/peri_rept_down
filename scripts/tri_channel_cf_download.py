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
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", help="single stock code, e.g. 600519")
    ap.add_argument("--stocks-file", help="text file with one stock code per line")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--token", default="", help="Tushare token (overrides env)")
    args = ap.parse_args()

    token = resolve_token(args.token)
    print(f"Token resolved, length: {len(token)}")

    # process_stock / build_merged_csv / build_report_html
    # 在后续 tasks 中添加


if __name__ == "__main__":
    main()