# -*- coding: utf-8 -*-
"""
从LibreOffice HTML完整提取三大财务报表
所有输出写入文件避免终端编码问题
"""
import os, json
from bs4 import BeautifulSoup

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
html_path = os.path.join(OUT_DIR, "lo_output", "002475_立讯精密_2025_年度报告.html")

with open(html_path, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
total = len(paragraphs)

# Debug: dump debug info to file
debug_file = os.path.join(OUT_DIR, "debug_paragraphs.txt")
with open(debug_file, "w", encoding="utf-8") as df:
    for i, p in enumerate(paragraphs):
        if p:
            df.write(f"[{i}] {p}\n")

def is_number(s):
    if not s: return False
    # Must NOT be a date or range
    if "-" in s and not s.startswith("-"):
        return False  # ranges like "10-50"
    if s.count(".") > 1:  # dates like "2023.03.20"
        return False
    if len(s.replace(",", "").replace(".", "").replace("-", "")) > 15:
        return False  # unreasonably long for a number
    cleaned = s.replace(",", "").replace("-", "").replace(".", "")
    if not cleaned.isdigit(): return False
    if not any(c.isdigit() for c in s): return False
    return True

# Find statement titles (they have 、 prefix like "、合并资产负债表")
title_keys = ["、合并资产负债表", "合并资产负债表", "、资产负债表", "资产负债表",
              "、合并利润表", "合并利润表", "、利润表", "利润表",
              "、合并现金流量表", "合并现金流量表", "、现金流量表", "现金流量表"]

title_indices = {}
for t in title_keys:
    for i, p in enumerate(paragraphs):
        if p == t:
            title_indices[t] = i

with open(os.path.join(OUT_DIR, "debug_findings.txt"), "w", encoding="utf-8") as df:
    for t, i in sorted(title_indices.items(), key=lambda x: x[1]):
        df.write(f"[{i}] {t}\n")

# Map to standard names
def find_best_title(indices, candidates):
    for cand in candidates:
        if cand in indices:
            return indices[cand]
    return -1

bs_start = find_best_title(title_indices, ["、合并资产负债表", "合并资产负债表", "、资产负债表", "资产负债表"])
is_start = find_best_title(title_indices, ["、合并利润表", "合并利润表", "、利润表", "利润表"])
cf_start = find_best_title(title_indices, ["、合并现金流量表", "合并现金流量表", "、现金流量表", "现金流量表"])

print(f"BS start: [{bs_start}]")
print(f"IS start: [{is_start}]")
print(f"CF start: [{cf_start}]")

def extract_table(paragraphs, start_idx, name):
    """
    Extract from title position. Structure:
    [title]
    [编制单位...]
    [year info lines]
    [单位：元]
    [项目]
    [期末余额]
    [期初余额]
    [流动资产：]
    [货币资金]
    [1,234,567.89]  <- 期末
    [987,654.32]     <- 期初
    [结算备付金]
    [0.00]
    [0.00]
    ...
    [流动资产合计]
    [期末值]
    [期初值]
    ...
    """
    # Scan forward from title to find table start (项目 header)
    table_start = -1
    for i in range(start_idx, min(start_idx + 30, total)):
        if paragraphs[i] == "项目":
            table_start = i
            break

    if table_start < 0:
        print(f"[ERROR] {name}: 未找到表头")
        return {}

    # Skip header rows: 项目, 期末余额, 期初余额, plus empty
    pos = table_start + 1
    while pos < total and paragraphs[pos] in ("项目", "期末余额", "期初余额", "期末数", "期初数", "本期金额", "上期金额", ""):
        pos += 1

    items = {}
    current_label = None
    skip_domains = ["立讯精密", "年度报告全文", "公告编号", "法定代表人",
                     "主管会计工作", "会计机构负责人", "年年报", "公司负责人"]

    def is_section_header(t):
        """Section headers end with ：or :"""
        return t.endswith("：") or t.endswith(":")

    def is_boring_text(t):
        """Text that's not a financial label"""
        if len(t) < 2: return True
        if t.isascii(): return True  # pure ASCII is not a Chinese label
        if "附注" in t: return True
        return False

    while pos < total:
        p = paragraphs[pos]
        pos += 1

        if not p: continue

        # Skip page numbers
        if p.isdigit() and len(p) <= 3: continue
        # Skip page headers
        if any(kw in p for kw in skip_domains): continue
        # Stop at end markers
        if p in ("法定代表人：", "主管会计工作负责人：", "会计机构负责人：",
                 "上年年末余额", "其他综合收益", "会计政策变更", "前期差错更正"):
            break

        if is_number(p):
            val = float(p.replace(",", ""))
            if current_label is not None and current_label not in items:
                items[current_label] = val
                current_label = None  # consumed
            # else: this is the second number (prior period), skip it
        else:
            # Only accept as label if it's a reasonable financial item name
            if is_section_header(p):
                current_label = None  # section headers have no value
            elif is_boring_text(p):
                current_label = None
            else:
                current_label = p

    print(f"[OK] {name}: {len(items)} items")
    return items


statements = {}

for name, start, stmt_type in [
    ("合并资产负债表", bs_start, "资产负债表"),
    ("合并利润表", is_start, "利润表"),
    ("合并现金流量表", cf_start, "现金流量表"),
]:
    if start >= 0:
        data = extract_table(paragraphs, start, name)
        statements[stmt_type] = data
    else:
        print(f"[NO] {name} not found")

# Save raw extracted data
out_path = os.path.join(OUT_DIR, "luxun_precision_2025_pdf_detail.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(statements, f, ensure_ascii=False, indent=2)

# Also print summary to file
summary_path = os.path.join(OUT_DIR, "extraction_summary.txt")
with open(summary_path, "w", encoding="utf-8") as sf:
    for stmt, items in statements.items():
        sf.write(f"{'='*70}\n")
        sf.write(f"  {stmt} ({len(items)} items)\n")
        sf.write(f"{'='*70}\n")
        sorted_i = sorted(items.items(), key=lambda x: x[0])
        for k, v in sorted_i:
            if abs(v) >= 1e8:
                sf.write(f"  {k:45s} {v:>20.2f}  ({v/1e8:.2f}亿)\n")
            elif v == 0:
                sf.write(f"  {k:45s} {v:>20.2f}\n")
            else:
                sf.write(f"  {k:45s} {v:>20.2f}\n")

print(f"\nSaved to: {out_path}")
print(f"Summary: {summary_path}")
print(f"BS items: {len(statements.get('资产负债表', {}))}")
print(f"IS items: {len(statements.get('利润表', {}))}")
print(f"CF items: {len(statements.get('现金流量表', {}))}")
