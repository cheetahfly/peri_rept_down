# -*- coding: utf-8 -*-
"""
精准提取LO HTML中的三大财务报表
处理多段落标签合并、识别表格起止边界
"""
import os, json, re
from bs4 import BeautifulSoup

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
html_path = os.path.join(OUT_DIR, "lo_output", "002475_立讯精密_2025_年度报告.html")

with open(html_path, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")
paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]

def extract_table(precise_range):
    """
    Extract table within a precise paragraph range.
    Table has 3-line pattern per row: label, val_current, val_prior.
    Multi-paragraph labels are concatenated.

    Returns dict of {label: current_value}
    """
    start, end = precise_range
    items = {}
    i = start

    # Find 项目 header
    while i < end and paragraphs[i] != "项目":
        i += 1
    if i >= end:
        return items

    # Skip header rows
    i += 1
    while i < end and paragraphs[i] in ("项目", "期末余额", "期初余额", "期末数", "期初数", "本期金额", "上期金额", ""):
        i += 1

    # Process rows
    while i < end:
        p = paragraphs[i]

        # Skip page markers
        if not p:
            i += 1
            continue
        if p.isdigit() and len(p) <= 3:
            i += 1
            continue
        if any(kw in p for kw in ["立讯精密", "年度报告全文", "公告编号"]):
            i += 1
            continue

        # Check for end of table
        if p in ("法定代表人：", "主管会计工作负责人：", "会计机构负责人：",
                 "单位负责人：", "财会负责人：", "复核：", "制表：",
                 "本期发生同一控制下企业合并的"):
            break

        # Check if this line starts a multi-paragraph label
        # A label ends when we encounter a number
        label_parts = []
        while i < end and not _is_number(paragraphs[i]) and paragraphs[i]:
            p2 = paragraphs[i]
            if p2.isdigit() and len(p2) <= 3:
                i += 1
                break  # page number, previous was part of label
            if any(kw in p2 for kw in ["立讯精密", "年度报告全文", "公告编号"]):
                i += 1
                continue
            if p2 in ("法定代表人：", "主管会计工作负责人：", "会计机构负责人：", "项目"):
                break
            label_parts.append(p2)
            i += 1

        if not label_parts:
            i += 1
            continue

        # Merge label parts, removing empty/noise fragments
        clean_parts = []
        for part in label_parts:
            part = part.strip()
            if not part: continue
            if part in ('"', '"', '“', '”', '‘', '’', ' ', '-'): continue
            if part.isdigit() and len(part) <= 3: continue
            clean_parts.append(part)

        label = "".join(clean_parts) if clean_parts else None
        if not label:
            i += 1
            continue

        # Skip section headers (end with ：)
        if label.endswith("：") or label.endswith(":"):
            continue

        # Skip headers
        if label in ("项目", "本期金额", "上期金额", "期末余额", "期初余额"):
            continue

        # Now try to get the current period value
        # Skip empty paragraphs
        while i < end and not paragraphs[i]:
            i += 1

        if i >= end: break

        val_str = paragraphs[i]
        if _is_number(val_str):
            val = float(val_str.replace(",", ""))
            # Skip values that look like year references
            if 2000 < val < 2099 and val == int(val):
                i += 1
                continue
            items[label] = val
            i += 1  # skip the current year value
            # Also skip the prior year value
            while i < end and not paragraphs[i]:
                i += 1
            if i < end and _is_number(paragraphs[i]):
                i += 1  # skip prior year value
        # else: Not a number, this label has no value (section header)

    return items


def _is_number(s):
    if not s: return False
    if "-" in s and not s.startswith("-"): return False
    if s.count(".") > 1: return False
    cleaned = s.replace(",", "").replace("-", "").replace(".", "")
    if not cleaned.isdigit(): return False
    if not any(c.isdigit() for c in s): return False
    return True


# Find section boundaries by looking for titles in the text
all_text = "\n".join(paragraphs)

# Dynamic boundary detection — search for parent-company section titles as end markers
def find_dynamic_sections():
    """Search for section titles in paragraph list to determine boundaries dynamically."""
    # Target: for each statement, find the "项目" header and the next parent-company title
    parent_titles = {
        "利润表": "母公司利润表",
        "资产负债表": "母公司资产负债表",
        "现金流量表": "母公司现金流量表",
    }
    # Also look for standalone titles
    stmt_titles = {
        "资产负债表": ["、合并资产负债表", "合并资产负债表", "、资产负债表", "资产负债表"],
        "利润表": ["、合并利润表", "合并利润表", "、利润表", "利润表"],
        "现金流量表": ["、合并现金流量表", "合并现金流量表", "、现金流量表", "现金流量表"],
    }

    result = {}
    for stmt_name, titles in stmt_titles.items():
        # Find the statement title position
        title_pos = -1
        for t in titles:
            try: title_pos = paragraphs.index(t); break
            except ValueError: continue
        if title_pos < 0:
            continue

        # Find the "项目" header after the title
        project_pos = -1
        for i in range(title_pos, min(title_pos + 50, len(paragraphs))):
            if paragraphs[i] == "项目":
                project_pos = i
                break
        if project_pos < 0:
            continue

        # Find next parent-company title as end boundary
        end_marker = parent_titles.get(stmt_name)
        end_pos = len(paragraphs)  # default: end of doc
        if end_marker:
            for i in range(project_pos + 1, len(paragraphs)):
                if paragraphs[i] == end_marker:
                    end_pos = i
                    break

        # Pad start a bit before 项目 for safety
        result[stmt_name] = (max(0, project_pos - 20), end_pos)

    return result

# Try dynamic detection first, fall back to hardcoded ranges
dynamic_sections = find_dynamic_sections()
sections = dynamic_sections if len(dynamic_sections) >= 2 else {
    "资产负债表": (25880, 26326),     # end before 母公司资产负债表
    "利润表": (26681, 27049),         # end before 母公司利润表
    "现金流量表": (27314, 27564),     # end before 母公司现金流量表
}
if dynamic_sections:
    print("Using dynamic section boundaries:")
    for k, (s, e) in sorted(dynamic_sections.items()):
        print(f"  {k}: ({s}, {e})")

results = {}
for name, (start, end) in sections.items():
    print(f"Extracting {name} (paragraphs {start}-{end})...")
    items = extract_table((start, end))
    results[name] = items
    print(f"  Found {len(items)} items")

# Save and also print to console-friendly file
out_path = os.path.join(OUT_DIR, "luxun_precision_2025_pdf_clean.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

summary_path = os.path.join(OUT_DIR, "extraction_clean_summary.txt")
with open(summary_path, "w", encoding="utf-8") as f:
    for name, items in results.items():
        f.write(f"{'='*70}\n{name} ({len(items)} items)\n{'='*70}\n")
        sorted_i = sorted(items.items(), key=lambda x: x[0])
        for k, v in sorted_i:
            if abs(v) >= 1e8:
                f.write(f"  {k:45s} {v:>20.2f}  ({v/1e8:.2f}亿)\n")
            elif v == 0:
                f.write(f"  {k:45s} {v:>20.2f}\n")
            else:
                f.write(f"  {k:45s} {v:>20.2f}\n")

print(f"\nSaved to {out_path}")
print(f"Summary: {summary_path}")
