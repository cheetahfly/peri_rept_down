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


_PREFIX_TOKENS = ("一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、",
                  "加：", "减：", "其中：", "其中:", "加:", "减:")

# 去括号注释（中文/英文）：'公允价值变动损失（收益以"－"号填列）' → '公允价值变动损失'
_BRACKET_RE = __import__("re").compile(r"[（(].*?[）)]")


def _normalize_name(name):
    """字符串规范化：去前缀序号/冠词、去空格、去冒号、去括号注释、统一'现金'↔'现金及现金等价物'同义。"""
    if not name:
        return ""
    s = name
    for p in _PREFIX_TOKENS:
        if s.startswith(p):
            s = s[len(p):]
    # 去除任意括号注释（"（收益以「－」号填列）"等）
    s = _BRACKET_RE.sub("", s)
    s = s.replace(" ", "").replace("：", "").replace(":", "")
    # '现金及现金等价物' 与 '现金' 同义（在期初/期末余额项目中）
    s = s.replace("现金及现金等价物", "现金")
    # '油气资产折耗、生产性生物资产折旧' 常被截断，做关键词归一
    s = s.replace("油气资产折耗", "").replace("生产性生物资产折旧", "")
    # 标点统一
    s = s.replace("，", "").replace(",", "").replace("、", "")
    return s


def best_match_by_name(rds_name, pdf_data):
    """按字符串相似度匹配；返回 (matched_name, value) 或 (None, None)。

    匹配策略（按优先级）：
    1. 完全相同
    2. 规范化（去前缀序号/冒号/空格、'现金'/'现金及现金等价物' 同义）后相等
    3. 子串包含（rds 名是 pdf 名的子串，反向亦然）
    """
    if rds_name in pdf_data:
        return rds_name, pdf_data[rds_name]
    norm_rds = _normalize_name(rds_name)
    if not norm_rds:
        return None, None
    # Pass 2: normalized equality
    for name, v in pdf_data.items():
        if _normalize_name(name) == norm_rds:
            return name, v
    # Pass 3: substring match (rds is in pdf name, or pdf name is in rds)
    for name, v in pdf_data.items():
        npdf = _normalize_name(name)
        if not npdf:
            continue
        if norm_rds in npdf or npdf in norm_rds:
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


def analyze_failure_modes(summary_path, out_md_path):
    """聚合 'no_match' 与 'large_error'，输出 top 失败项目清单"""
    import collections
    with open(summary_path, "r", encoding="utf-8") as f:
        results = json.load(f)
    no_match_counter = collections.Counter()
    no_match_examples = {}  # rds_name -> [(stock_code, rds_value)]
    large_err_counter = collections.Counter()
    large_err_examples = {}  # rds_name -> [(stock_code, rds_value, pdf_value, abs_diff)]
    placeholder_neg_55x = []  # rds_name -> [(stock, value)]
    for r in results:
        if r.get("status") != "OK":
            continue
        for d in r.get("details", []):
            if d["class"] == "no_match":
                no_match_counter[d["rds_name"]] += 1
                no_match_examples.setdefault(d["rds_name"], []).append(
                    (r["stock_code"], d["rds_value"])
                )
            elif d["class"] == "large_error":
                large_err_counter[d["rds_name"]] += 1
                large_err_examples.setdefault(d["rds_name"], []).append(
                    (r["stock_code"], d["rds_value"], d["pdf_value"], d["abs_diff"])
                )
                pv = d.get("pdf_value")
                if isinstance(pv, (int, float)) and -570 < pv < -540:
                    placeholder_neg_55x.append(
                        (d["rds_name"], r["stock_code"], pv)
                    )
    with open(out_md_path, "w", encoding="utf-8") as f:
        f.write("# PDF 提取失败模式分析\n\n")
        f.write(f"基线: 7 只股票 × 2020 年报，分析自 `{summary_path}`\n\n")
        f.write("## A. 占位符 bug（pdf_value ∈ [-570, -540]）\n\n")
        if placeholder_neg_55x:
            f.write(f"发现 {len(placeholder_neg_55x)} 个 large_error 是 extractor 输出的 -55x 占位符（疑似页码相关 sentinel 泄露）：\n\n")
            for name, stock, v in placeholder_neg_55x:
                f.write(f"- ({stock}) {name} → pdf_value={v}\n")
        else:
            f.write("无\n")
        f.write("\n## B. Top 20 'no_match' (PDF 中没找到对应 RDS 项目)\n\n")
        f.write("| 出现次数 | RDS 项目名 | 示例(股票:RDS值) |\n|---:|---|---|\n")
        for name, cnt in no_match_counter.most_common(20):
            examples = no_match_examples.get(name, [])[:3]
            ex_str = ", ".join(f"{s}:{v:,.0f}" for s, v in examples if v is not None)
            f.write(f"| {cnt} | {name} | {ex_str} |\n")
        f.write("\n## C. Top 20 'large_error' (找到但值差很多)\n\n")
        f.write("| 次数 | RDS 项目名 | 示例(股票:RDS→PDF, diff) |\n|---:|---|---|\n")
        for name, cnt in large_err_counter.most_common(20):
            examples = large_err_examples.get(name, [])[:2]
            ex_str = "; ".join(
                f"{s}:{rv:,.0f}→{pv:,.0f}, Δ={d:,.0f}"
                for s, rv, pv, d in examples
                if rv is not None and pv is not None
            )
            f.write(f"| {cnt} | {name} | {ex_str} |\n")



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

    # 失败模式分析
    failure_md = os.path.join(OUT_DIR, "_failure_modes.md")
    analyze_failure_modes(out_path, failure_md)
    print(f"Failure modes: {failure_md}")


if __name__ == "__main__":
    main()
