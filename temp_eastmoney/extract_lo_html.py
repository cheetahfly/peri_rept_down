# -*- coding: utf-8 -*-
"""
从LibreOffice生成的HTML提取立讯精密2025三大表完整细项
"""
import sys, os, json, re
from bs4 import BeautifulSoup

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
html_path = os.path.join(OUT_DIR, "lo_output")

# Find the LO-generated HTML
html_file = None
for f in os.listdir(html_path):
    if f.endswith(".html"):
        html_file = os.path.join(html_path, f)
        break

if not html_file:
    # Try generating again
    import subprocess, pathlib
    pdf_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
        "..", "data", "by_code", "002475", "002475_立讯精密_2025_年度报告.PDF"))
    result = subprocess.run([
        "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
        "--headless", "--convert-to", "html",
        "--outdir", str(pathlib.Path(html_path)), str(pathlib.Path(pdf_path))
    ], capture_output=True, timeout=300)
    print(f"LO return: {result.returncode}")
    for f in os.listdir(html_path):
        if f.endswith(".html"):
            html_file = os.path.join(html_path, f)
            break

print(f"HTML file: {html_file}")
print(f"Size: {os.path.getsize(html_file)/1024:.0f}KB")

with open(html_file, "r", encoding="utf-8") as f:
    content = f.read()

soup = BeautifulSoup(content, "html.parser")

# LO Draw HTML: each draw:text span has position info
# Financial statements are usually in landscape pages
# Extract all text elements with positions
elements = []
for span in soup.find_all(["span", "div"], string=True):
    text = span.get_text(strip=True)
    if not text:
        continue
    style = span.get("style", "")
    # Parse position from style
    x, y = 0, 0
    m = re.search(r'left:(\d+)pt', style)
    if m: x = int(m.group(1))
    m = re.search(r'top:(\d+)pt', style)
    if m: y = int(m.group(1))
    # Font size
    sz = 12
    m = re.search(r'font-size:(\d+)pt', style)
    if m: sz = int(m.group(1))
    elements.append({"text": text, "x": x, "y": y, "size": sz})

print(f"Total elements: {len(elements)}")

# Sort by y then x
elements.sort(key=lambda e: (e["y"], e["x"]))

# Find page boundaries (large y jumps indicate new page)
pages = []
current_page = []
last_y = 0
for e in elements:
    if current_page and e["y"] < last_y - 100:  # new page
        pages.append(current_page)
        current_page = []
    current_page.append(e)
    last_y = e["y"]
if current_page:
    pages.append(current_page)

print(f"Detected pages: {len(pages)}")

# Find financial statement pages
def find_statement_pages(pages, keywords):
    """Find pages containing section titles"""
    result = []
    for idx, page in enumerate(pages):
        text = " ".join(e["text"] for e in page)
        for kw in keywords:
            if kw in text:
                result.append(idx)
                break
    return result

bs_pages_idx = find_statement_pages(pages, ["资产负债表", "合并资产负债表"])
is_pages_idx = find_statement_pages(pages, ["利润表", "合并利润表"])
cf_pages_idx = find_statement_pages(pages, ["现金流量表", "合并现金流量表"])

print(f"\n资产负债表页: {bs_pages_idx[:5]}")
print(f"利润表页: {is_pages_idx[:5]}")
print(f"现金流量表页: {cf_pages_idx[:5]}")

# Extract table data from a range of pages
def extract_table_from_pages(pages, start_idx, end_idx):
    """Extract structured data from page range"""
    items = {}
    for idx in range(start_idx, min(end_idx + 1, len(pages))):
        page = pages[idx]
        # Group elements into lines by y-coordinate (within 10pt tolerance)
        lines = {}
        for e in page:
            y_key = round(e["y"] / 10) * 10
            if y_key not in lines:
                lines[y_key] = []
            lines[y_key].append(e)

        # Sort lines by y
        for y_key in sorted(lines.keys()):
            elems = sorted(lines[y_key], key=lambda e: e["x"])
            full_text = " ".join(e["text"] for e in elems)

            # Try to extract label + value pairs
            # Pattern: Chinese text followed by numbers (possibly with commas, dots, minus)
            # LO export often has label and value as separate spans but on same line
            nums = re.findall(r'-?[\d,]+\.?\d*', full_text)
            if nums:
                # Remove number parts to get label
                label = full_text
                for n in nums:
                    label = label.replace(n, "", 1)
                label = label.strip()
                if label and len(nums) >= 2:
                    # Usually: label, this_year, last_year
                    val = float(nums[-2].replace(",", ""))
                    items[label] = val

    return items

# Actually, let me use a smarter approach:
# Find the exact table boundaries using the page's text content

def extract_financial_table(pages, all_pages, label, max_pages=4):
    """Try to extract a complete financial statement"""
    if not pages:
        return {}

    start_page = pages[0]
    end_page = start_page + max_pages

    print(f"\n{label}: extracting pages {start_page}-{end_page}")

    all_items = []
    for idx in range(start_page, min(end_page, len(all_pages))):
        page = all_pages[idx]
        # Group by y
        lines = {}
        for e in page:
            y_key = round(e["y"] / 10) * 10
            if y_key not in lines:
                lines[y_key] = []
            lines[y_key].append(e)

        page_items = []
        for y_key in sorted(lines.keys()):
            elems = sorted(lines[y_key], key=lambda e: e["x"])
            text = " ".join(e["text"] for e in elems)

            # Skip headers, footers
            if any(kw in text for kw in ["单位：", "元", "附注", "报表日期",
                "法定代表人", "主管会计工作负责人", "会计机构负责人",
                "第", "页", "年度报告", "公告编号"]):
                continue
            if len(text) < 2:
                continue

            # Extract number at end of line
            nums = re.findall(r'-?[\d,]+\.?\d*', text)
            if nums:
                # Remove the numbers from text to get label
                remaining = text
                for n in nums:
                    remaining = remaining.replace(n, "", 1)
                remaining = remaining.replace(" ", "").strip()
                if remaining and len(remaining) > 1:
                    val = float(nums[-1].replace(",", ""))
                    page_items.append((remaining, val, len(nums), text))

        # Try to find the actual table (items should have at least 2 numbers: current + prior year)
        table_items = [(l, v) for l, v, n, _ in page_items if n >= 2]
        if table_items:
            print(f"  Page {idx}: {len(page_items)} potential items, {len(table_items)} with 2+ numbers")
            all_items.extend(table_items)
        else:
            print(f"  Page {idx}: {len(page_items)} items (no multi-number rows)")

    return dict(all_items)


# Extract all three statements
statements = {
    "利润表": extract_financial_table(is_pages_idx, pages, "利润表"),
    "资产负债表": extract_financial_table(bs_pages_idx, pages, "资产负债表"),
    "现金流量表": extract_financial_table(cf_pages_idx, pages, "现金流量表"),
}

# Print results and save
all_combined = {}
for name, items in statements.items():
    print(f"\n{'='*70}")
    print(f"  {name} ({len(items)} items)")
    print(f"{'='*70}")
    sorted_items = sorted(items.items(), key=lambda x: x[0])
    for k, v in sorted_items:
        if abs(v) >= 1e8:
            print(f"  {k:45s} {v:>20.2f}  ({v/1e8:.2f}亿)")
        else:
            print(f"  {k:45s} {v:>20.2f}")

    all_combined[name] = items

out_path = os.path.join(OUT_DIR, "luxun_precision_2025_pdf_full.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(all_combined, f, ensure_ascii=False, indent=2, default=str)
print(f"\nSaved to: {out_path}")
print(f"\nTotal items: 利润表={len(statements['利润表'])}, 资产负债表={len(statements['资产负债表'])}, 现金流量表={len(statements['现金流量表'])}")
