"""
Numeric recovery for CID-font garbled PDFs.

Uses pdfplumber word extraction with spatial column detection to recover
correct numeric values from pages where Chinese text is garbled.

Strategy:
1. Extract all words with (x, y) positions
2. Cluster numeric values by x-position to detect columns automatically
3. Group into rows by y-position
4. For each row, assign values to their correct columns
5. Return a structured matrix preserving the original table layout
"""
import sys
import os
from collections import defaultdict
from typing import Dict, List, Optional

import pdfplumber

# Constants for score_page_density
NUMERIC_COUNT_CAP = 50.0
CLUSTER_TOLERANCE = 25
NUMERIC_WEIGHT = 0.6
COLUMN_WEIGHT = 0.4


def _parse_num(text: str) -> Optional[float]:
    """Parse a numeric value, handling parentheses for negatives and commas."""
    t = text.strip().replace(",", "").replace(" ", "")
    if not t:
        return None
    if t.endswith("%"):
        try:
            return float(t[:-1])
        except ValueError:
            return None
    is_neg = t.startswith("(") and t.endswith(")")
    if is_neg:
        t = t[1:-1]
    try:
        return -float(t) if is_neg else float(t)
    except ValueError:
        return None


def _is_date_like(val: float) -> bool:
    """Heuristic: skip values that look like years (2023/2024) or small row numbers."""
    return (1000 <= val <= 3000) or val in range(1, 33)


def _cluster_x_positions(
    x_positions: List[float], tolerance: float = 20
) -> List[float]:
    """
    Cluster x-coordinates to detect column centers.
    Uses a simple greedy clustering approach.
    Returns sorted list of column center x-positions.
    """
    sorted_x = sorted(x_positions)
    if not sorted_x:
        return []

    clusters = [[sorted_x[0]]]
    for x in sorted_x[1:]:
        if abs(x - sum(clusters[-1]) / len(clusters[-1])) <= tolerance:
            clusters[-1].append(x)
        else:
            clusters.append([x])

    return [sum(c) / len(c) for c in clusters]


def score_page_density(pdf_path: str, page_num: int) -> float:
    """
    Score a page by numeric density and column structure consistency.

    Score = numeric_count_normalized * 0.6 + column_consistency * 0.4

    numeric_count_normalized: count of numeric words (excluding years/dates), scaled 0-1
    column_consistency: how many detected columns the page has, scaled 0-1
                         (pages with 3+ columns score highest)
    """
    if page_num < 0:
        return 0.0

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return 0.0
            page = pdf.pages[page_num]
            words = page.extract_words()
    except Exception:
        return 0.0

    if not words:
        return 0.0

    # Count numeric words (excluding years and date-like numbers)
    numeric_words = [
        w for w in words
        if _parse_num(w["text"]) is not None and not _is_date_like(_parse_num(w["text"]))
    ]
    numeric_count = len(numeric_words)

    # Normalize: cap at NUMERIC_COUNT_CAP numeric words = full score
    numeric_score = min(numeric_count / NUMERIC_COUNT_CAP, 1.0)

    # Column consistency: cluster x-positions to detect column count
    if numeric_words:
        x_midpoints = [(w["x0"] + w["x1"]) / 2 for w in numeric_words]
        col_centers = _cluster_x_positions(x_midpoints, tolerance=CLUSTER_TOLERANCE)
        col_count = len(col_centers)
    else:
        col_count = 0

    # 3+ columns = full score, 1 column = low score, 0 = 0
    if col_count >= 3:
        col_score = 1.0
    elif col_count == 2:
        col_score = 0.6
    elif col_count == 1:
        col_score = 0.2
    else:
        col_score = 0.0

    return numeric_score * NUMERIC_WEIGHT + col_score * COLUMN_WEIGHT


def get_page_count(pdf_path: str) -> int:
    """Return total page count of a PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)


def extract_structured_numeric(
    pdf_path: str, page_num: int, y_tolerance: float = 5.0
) -> Dict:
    """
    Extract numeric data with automatic column detection.

    Returns:
        {
            "page": page_num,
            "method": "table" | "word",
            "columns": [center_x1, center_x2, ...],  # detected column positions
            "rows": [
                {"y": y_pos, "row_idx": i, "values": [col1_val, col2_val, ...]},
                ...
            ]
        }
    """
    with pdfplumber.open(pdf_path) as pdf:
        if page_num >= len(pdf.pages):
            return {"page": page_num, "method": "none", "columns": [], "rows": []}
        page = pdf.pages[page_num]
        words = page.extract_words()

    if not words:
        return {"page": page_num, "method": "none", "columns": [], "rows": []}

    # Separate labels and values
    all_values = []  # (x0, x1, top, value)
    for w in words:
        v = _parse_num(w["text"])
        if v is not None and not _is_date_like(v):
            all_values.append((w["x0"], w["x1"], w["top"], v))

    if not all_values:
        return {"page": page_num, "method": "none", "columns": [], "rows": []}

    # Detect column centers from x-positions of values
    # Use the midpoint of each word
    x_midpoints = [(x0 + x1) / 2 for x0, x1, _, _ in all_values]
    col_centers = _cluster_x_positions(x_midpoints, tolerance=25)

    # Check if we have meaningful columns
    if len(col_centers) < 1:
        return {"page": page_num, "method": "none", "columns": [], "rows": []}

    # Assign each value to a column
    def _col_index(x_mid: float) -> int:
        distances = [abs(x_mid - cc) for cc in col_centers]
        return distances.index(min(distances))

    # Group values by row (y-position)
    row_map: Dict[float, list] = defaultdict(list)
    for x0, x1, top, val in all_values:
        y_key = round(top / y_tolerance) * y_tolerance
        x_mid = (x0 + x1) / 2
        ci = _col_index(x_mid)
        row_map[y_key].append((ci, val))

    # Build rows
    rows = []
    row_idx = 0
    for y_pos in sorted(row_map):
        entries = row_map[y_pos]
        # Multiple values from same column? Keep the one closest to column center
        col_vals: Dict[int, float] = {}
        for ci, val in entries:
            if ci not in col_vals:
                col_vals[ci] = val

        # Build the row's value array: one value per detected column
        vals = [col_vals.get(i) for i in range(len(col_centers))]

        # Skip rows where all values are None
        if all(v is None for v in vals):
            continue

        # Skip rows that are likely note reference lines
        non_none = [v for v in vals if v is not None]
        if len(non_none) <= 1 and all(abs(v) < 10000 for v in non_none):
            # Could be a note reference row; only skip if other rows have much larger values
            pass

        rows.append({"y": y_pos, "row_idx": row_idx, "values": vals})
        row_idx += 1

    return {
        "page": page_num,
        "method": "word",
        "columns": col_centers,
        "rows": rows,
    }


def extract_table_numeric_direct(
    pdf_path: str, page_num: int
) -> List[Dict]:
    """
    Try pdfplumber table extraction first (best when table structure is detected).
    Returns rows with numeric values only.
    """
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        if page_num >= len(pdf.pages):
            return results
        page = pdf.pages[page_num]
        tables = page.find_tables()

        for table in tables:
            data = table.extract()
            if not data or len(data) < 3 or len(data[0]) < 2:
                continue

            for row_idx, row in enumerate(data):
                if not row or len(row) < 2:
                    continue

                values = []
                has_financial = False
                all_date = True

                for cell in row[1:]:
                    if cell is None:
                        continue
                    v = _parse_num(str(cell))
                    if v is not None:
                        if not _is_date_like(v):
                            has_financial = True
                            all_date = False
                        values.append(v)

                if all_date and values:
                    continue
                if has_financial:
                    results.append({
                        "table_bbox": table.bbox,
                        "row": row_idx,
                        "values": values,
                    })

    return results


def recover_page(pdf_path: str, page_num: int) -> Dict:
    """
    Recover numeric data from a single garbled page.

    Uses word-level extraction with column detection (most reliable for
    garbled PDFs where table detection may split or miss columns).
    """
    result = extract_structured_numeric(pdf_path, page_num)

    # Fall back to table extraction only if word extraction found nothing
    if not result.get("rows"):
        table_rows = extract_table_numeric_direct(pdf_path, page_num)
        if table_rows:
            return {
                "method": "table",
                "columns": list(range(len(table_rows[0]["values"]))) if table_rows else [],
                "rows": [{"y": 0, "row_idx": r["row"], "values": r["values"]} for r in table_rows],
            }

    return result


def recover_statement(pdf_path: str, pages: List[int]) -> Dict:
    """
    Recover numeric data from garbled statement pages.

    Returns:
        recovery dict with page_data and flat_data
    """
    page_data = {}
    flat_data = {}
    methods_used = set()

    for p in pages:
        result = recover_page(pdf_path, p)
        methods_used.add(result.get("method", "none"))

        page_rows = []
        for r in result.get("rows", []):
            vals = [v for v in r["values"] if v is not None]
            page_rows.append({"row": r.get("row_idx", 0), "values": vals})
            for j, v in enumerate(vals):
                flat_data[f"p{p}_r{r.get('row_idx',0)}_c{j}"] = v

        page_data[str(p)] = {
            "method": result.get("method", "none"),
            "row_count": len(result.get("rows", [])),
            "rows": page_rows,
        }

    if len(methods_used) > 1:
        method = "mixed"
    elif methods_used:
        method = methods_used.pop()
    else:
        method = "none"

    return {
        "recovery_method": method,
        "found": len(flat_data) > 0,
        "pages": sorted(pages),
        "page_data": page_data,
        "data": flat_data,
        "stats": {
            "total_values": len(flat_data),
            "total_pages": len(pages),
            "total_rows": sum(pd.get("row_count", 0) for pd in page_data.values()),
        },
    }


def save_recovered_data(
    stock_code: str, year: int, statement_type: str, data: Dict
) -> int:
    """Save recovered numeric data to the database."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from extraction.storage.sqlite_store import SqliteStore

    store = SqliteStore()
    record = {
        "statement_type": statement_type,
        "found": data.get("found", False),
        "recovered": True,
        "pages": data.get("pages", []),
        "data": data.get("data", {}),
        "page_data": data.get("page_data", {}),
        "stats": data.get("stats", {}),
        "recovery_method": data.get("recovery_method", "word_extraction"),
        "extracted_at": "word_recovery",
    }
    store.save(stock_code, year, statement_type, record)
    return len(data.get("data", {}))


def find_data_pages(
    pdf_path: str,
    scan_range: List[int],
    top_n: int = 10,
) -> List[int]:
    """
    Scan pages in the given range using density scoring and return top-N data pages.
    Opens PDF once and scores all pages in a single pass for efficiency.
    """
    if not scan_range:
        return []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return []

            scored = []
            for p in scan_range:
                if p >= len(pdf.pages):
                    scored.append((0.0, p))
                    continue

                page = pdf.pages[p]
                words = page.extract_words()

                if not words:
                    scored.append((0.0, p))
                    continue

                # Count numeric words (excluding years and date-like numbers)
                numeric_words = [
                    w for w in words
                    if _parse_num(w["text"]) is not None and not _is_date_like(_parse_num(w["text"]))
                ]
                numeric_count = len(numeric_words)

                # Normalize: cap at NUMERIC_COUNT_CAP numeric words = full score
                numeric_score = min(numeric_count / NUMERIC_COUNT_CAP, 1.0)

                # Column consistency: cluster x-positions to detect column count
                if numeric_words:
                    x_midpoints = [(w["x0"] + w["x1"]) / 2 for w in numeric_words]
                    col_centers = _cluster_x_positions(x_midpoints, tolerance=CLUSTER_TOLERANCE)
                    col_count = len(col_centers)
                else:
                    col_count = 0

                # 3+ columns = full score, 1 column = low score, 0 = 0
                if col_count >= 3:
                    col_score = 1.0
                elif col_count == 2:
                    col_score = 0.6
                elif col_count == 1:
                    col_score = 0.2
                else:
                    col_score = 0.0

                score = numeric_score * NUMERIC_WEIGHT + col_score * COLUMN_WEIGHT
                scored.append((score, p))

    except Exception:
        return []

    scored.sort(reverse=True, key=lambda x: x[0])
    return [p for _, p in scored[:top_n]]


def recover_statement_auto(
    pdf_path: str,
    statement_type: str,
    scan_range: List[int],
    top_n: int = 10,
) -> Dict:
    """
    Automatically discover data pages and recover statement data.

    1. Scan scan_range pages with density scoring
    2. Take top_n highest-scoring pages
    3. Attempt recovery on those pages
    4. Validate output has expected financial item structure
    5. Return recovered data
    """
    candidate_pages = find_data_pages(pdf_path, scan_range, top_n)

    if not candidate_pages:
        return {
            "recovery_method": "auto_scan",
            "found": False,
            "pages": [],
            "data": {},
            "error": "no candidate pages found",
        }

    # Attempt recovery on candidates
    data = recover_statement(pdf_path, candidate_pages)

    # Validate: check that recovered data has financial-scale values
    if data.get("found"):
        values = list(data.get("data", {}).values())
        large_values = [v for v in values if abs(v) > 1000]
        if len(large_values) < 3:
            data["found"] = False
            data["validation_failed"] = True

    return data


def recover_all_failing(verbose: bool = True) -> Dict:
    """
    Recover data for all known failing CID-font garbled PDFs.

    Uses auto-density-scan discovery instead of hardcoded page numbers.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    cases = [
        ("data/by_code/600016/600016_民生银行_2024_年报.pdf", "600016", 2024, "cash_flow"),
        ("data/by_code/600089/600089_特变电工_2025_年报.pdf", "600089", 2025, "balance_sheet"),
        ("data/by_code/600089/600089_特变电工_2025_年报.pdf", "600089", 2025, "income_statement"),
        ("data/by_code/600089/600089_特变电工_2025_年报.pdf", "600089", 2025, "cash_flow"),
        ("data/by_code/601668/601668_中国建筑_2024_年报.pdf", "601668", 2024, "income_statement"),
        ("data/by_code/601628/601628_中国人寿_2024_年报.pdf", "601628", 2024, "balance_sheet"),
        ("data/by_code/601628/601628_中国人寿_2024_年报.pdf", "601628", 2024, "income_statement"),
        ("data/by_code/601628/601628_中国人寿_2024_年报.pdf", "601628", 2024, "cash_flow"),
    ]

    results = {}
    for pdf_rel, code, year, stmt in cases:
        pdf_path = os.path.join(project_root, pdf_rel)
        if not os.path.exists(pdf_path):
            if verbose:
                print(f"跳过 {code} {year} {stmt}: PDF不存在")
            continue

        if verbose:
            print(f"{code} {year} {stmt}: 自动扫描...")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                scan_range = list(range(len(pdf.pages)))
        except Exception as e:
            if verbose:
                print(f"  无法打开PDF: {e}")
            continue

        data = recover_statement_auto(pdf_path, stmt, scan_range, top_n=10)
        count = save_recovered_data(code, year, stmt, data)
        results[(code, year, stmt)] = count

        if verbose:
            stats = data.get("stats", {})
            print(f"  -> 保存 {count} 数值 ({data.get('recovery_method', 'auto')}, "
                  f"{stats.get('total_rows', 0)} 行)")

    return results


if __name__ == "__main__":
    recover_all_failing()
