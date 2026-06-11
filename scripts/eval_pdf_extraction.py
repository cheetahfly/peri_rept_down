# -*- coding: utf-8 -*-
"""
PDF 提取质量评估：将 data/extracted/by_code/{stock}/{stock}_{year}_cash_flow.json
与 RDS 标准对比，统计精确率、覆盖率、间接法完整性。

测试样本：所有 data/pdfs/{stock}/{stock}_2020_annual.pdf 对应已提取的股票
基准：RDS cf_o.rds / cf_f.rds 的 2020 年报 CF 数据
"""
import os
import sys
import json
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extraction.ground_truth.rds_loader import RdsLoader

RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
EXTRACTED_DIR = "data/extracted/by_code"
OUT_DIR = "tmp/eval_pdf_extraction_2020"
os.makedirs(OUT_DIR, exist_ok=True)


def load_pdf_extracted(stock_code, year):
    """读取 PDF 提取结果，返回 {item_name_zh: value} 或 None

    兼容两种 JSON 结构：
    - Wrapped:  {stock_code, ..., data: {statement_type, found, pages, data: {item: v}, ...}}
    - Flat:     {statement_type, found, pages, data: {item: v}, extracted_at}
    """
    path = os.path.join(EXTRACTED_DIR, stock_code, f"{stock_code}_{year}_cash_flow.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        outer = json.load(f)
    # Wrapped: outer.data 仍是 dict 且含 statement_type → 再下钻一层
    inner = outer.get("data", {})
    if isinstance(inner, dict) and "statement_type" in inner and "data" in inner:
        field_map = inner.get("data", {})
    else:
        field_map = inner
    if not isinstance(field_map, dict):
        return None
    out = {}
    for name, v in field_map.items():
        if isinstance(v, (int, float)):
            out[name] = float(v)
        elif isinstance(v, str):
            try:
                out[name] = float(v.replace(",", ""))
            except ValueError:
                pass
    return out


def best_match_by_name(rds_name, pdf_data):
    """按字符串相似度匹配；返回 (matched_name, value) 或 (None, None)"""
    if rds_name in pdf_data:
        return rds_name, pdf_data[rds_name]
    # 简化匹配：去空格、冒号后再尝试
    norm_rds = rds_name.replace(" ", "").replace("：", "").replace(":", "")
    for name, v in pdf_data.items():
        if name.replace(" ", "").replace("：", "").replace(":", "") == norm_rds:
            return name, v
    return None, None


def evaluate_stock(stock_code, year=2020):
    loader = RdsLoader(RDS_DIR)
    tidy = loader.load_stock_data_tidy(stock_code, year, "cash_flow")
    rds_annual = [r for r in tidy if r["report_type"] == "annual" and r["value"] is not None]
    pdf_data = load_pdf_extracted(stock_code, year)
    if pdf_data is None:
        return {"stock_code": stock_code, "status": "PDF_NOT_EXTRACTED"}
    counters = {"exact": 0, "sub_yuan": 0, "rounded": 0, "large_error": 0, "no_match": 0}
    rows = []
    for item in rds_annual:
        name, val = best_match_by_name(item["item_name"], pdf_data)
        if val is None:
            counters["no_match"] += 1
            cls = "no_match"
            diff = None
            rel = None
        else:
            diff = abs(val - item["value"])
            rel = (diff / abs(item["value"]) * 100) if item["value"] != 0 else 0
            if diff < 0.01:
                cls = "exact"
                counters["exact"] += 1
            elif diff < 1.0:
                cls = "sub_yuan"
                counters["sub_yuan"] += 1
            elif rel < 1.0:
                cls = "rounded"
                counters["rounded"] += 1
            else:
                cls = "large_error"
                counters["large_error"] += 1
        rows.append({
            "rds_code": item["item_code"],
            "rds_name": item["item_name"],
            "rds_value": item["value"],
            "pdf_name": name,
            "pdf_value": val,
            "abs_diff": diff,
            "rel_err_pct": rel,
            "class": cls,
        })
    total = sum(counters.values())
    return {
        "stock_code": stock_code,
        "status": "OK",
        "rds_total": total,
        **counters,
        "exact_rate": round(counters["exact"] / total * 100, 2) if total else 0,
        "details": rows,
    }


def main():
    # 从 data/pdfs 推断已下载 PDF 的股票
    candidates = []
    pdf_root = "data/pdfs"
    for entry in os.listdir(pdf_root):
        d = os.path.join(pdf_root, entry)
        if os.path.isdir(d):
            pdf_path = os.path.join(d, f"{entry}_2020_annual.pdf")
            if os.path.exists(pdf_path):
                candidates.append(entry)
    print(f"Found {len(candidates)} stocks with 2020 PDF: {candidates}")

    results = []
    for stock_code in sorted(candidates):
        r = evaluate_stock(stock_code, 2020)
        results.append(r)
        if r["status"] == "OK":
            print(f"  {stock_code}: exact={r['exact']}/{r['rds_total']} ({r['exact_rate']}%)  "
                  f"no_match={r['no_match']}  large_error={r['large_error']}")
        else:
            print(f"  {stock_code}: {r['status']}")

    out_path = os.path.join(OUT_DIR, "_eval_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSummary: {out_path}")


if __name__ == "__main__":
    main()
