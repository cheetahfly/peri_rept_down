# -*- coding: utf-8 -*-
"""
直接用pdfplumber从立讯精密PDF中提取三大表细项
绕过HybridParser的HtmlConverter失败问题
"""
import sys, os, json, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
    "data", "by_code", "002475", "002475_立讯精密_2025_年度报告.PDF")

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

import pdfplumber

# Keywords to find financial statement pages
SECTION_KEYWORDS = {
    "balance_sheet": ["资产负债表"],
    "income_statement": ["利润表"],
    "cash_flow": ["现金流量表"],
}

results = {}

with pdfplumber.open(pdf_path) as pdf:
    total_pages = len(pdf.pages)
    print(f"Total pages: {total_pages}")

    # Step 1: Find the section pages for each financial statement
    section_pages = {k: [] for k in SECTION_KEYWORDS}

    for i in range(total_pages):
        page = pdf.pages[i]
        text = page.extract_text() or ""
        for stmt_type, keywords in SECTION_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    section_pages[stmt_type].append(i)
                    break

    for stmt_type, pages in section_pages.items():
        print(f"\n{stmt_type} found on pages: {pages[:10]}")

    # Step 2: For each statement, find the main table pages and extract all items
    for stmt_type, pages in section_pages.items():
        if not pages:
            continue

        # Find continuous block starting from first occurrence
        start_page = pages[0]
        end_page = start_page + 3  # assume 3-4 pages per statement
        if end_page > total_pages:
            end_page = total_pages

        print(f"\n{'='*70}")
        print(f"Extracting {stmt_type} from pages {start_page}-{end_page}")
        print(f"{'='*70}")

        all_lines = []
        for i in range(start_page, min(end_page + 2, total_pages)):
            page = pdf.pages[i]
            text = page.extract_text() or ""
            lines = text.split('\n')
            all_lines.extend([(i, l) for l in lines])

        # Extract key-value pairs from text lines
        items = {}
        for page_num, line in all_lines:
            line = line.strip()
            if not line:
                continue
            # Try to find numeric values at end of line
            # Pattern: Chinese text followed by numbers
            matches = re.findall(r'[\d,.-]+', line)
            if matches:
                # Get the last number (usually the current period value)
                last_num_str = matches[-1].replace(',', '')
                try:
                    val = float(last_num_str)
                    # Remove the number from the line to get the label
                    label = re.sub(r'[\d,.-]+', '', line).strip()
                    if label and len(label) > 1:
                        items[label] = val
                except ValueError:
                    pass

        # Print all items sorted
        print(f"Total items found: {len(items)}")
        sorted_items = sorted(items.items(), key=lambda x: x[0])
        for k, v in sorted_items:
            if abs(v) >= 1e8:
                print(f"  {k:45s} {v:>20.2f} ({v/1e8:.2f}亿)")
            else:
                print(f"  {k:45s} {v:>20.2f}")

        results[stmt_type] = {
            "pages": list(range(start_page, min(end_page + 2, total_pages))),
            "items": items,
        }

# Save results
out_path = os.path.join(OUT_DIR, "luxun_precision_2025_pdf_direct.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\nSaved to: {out_path}")
