# -*- coding: utf-8 -*-
"""
Shared library for EM channel evaluation.
"""

import json
import os
import random
import re
import time
import warnings
from typing import Dict, List, Optional, Tuple

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

warnings.filterwarnings("ignore")

# ----- 板块代码前缀映射 -----
BOARD_PREFIXES: Dict[str, Tuple[str, ...]] = {
    "sh_main": ("600", "601", "603", "605"),  # 沪市主板
    "sz_main": ("000", "001", "002"),          # 深市主板（排除 003/300/301）
    "chinext": ("300", "301"),                 # 创业板
    "star":    ("688", "689"),                 # 科创板
}


def classify_board(stock_code: str) -> str:
    """Classify a stock code to one of 4 boards.

    Returns one of: sh_main, sz_main, chinext, star, unknown.
    """
    code = str(stock_code).zfill(6)
    for board, prefixes in BOARD_PREFIXES.items():
        for prefix in prefixes:
            if code.startswith(prefix):
                return board
    return "unknown"


def stratified_sample(
    stock_list: List[str],
    per_board: int = 50,
    seed: int = 42,
) -> Dict:
    """Stratified random sample: per_board stocks from each of 4 boards.

    Args:
        stock_list: full A-share stock codes.
        per_board: how many to sample from each board (default 50).
        seed: random seed for reproducibility.

    Returns:
        {
            "seed": 42,
            "per_board": 50,
            "boards": {"sh_main": [...], "sz_main": [...], "chinext": [...], "star": [...]},
            "all_codes": [所有抽到的代码]
        }
    """
    by_board: Dict[str, List[str]] = {b: [] for b in BOARD_PREFIXES}
    for code in stock_list:
        board = classify_board(code)
        if board in by_board:
            by_board[board].append(code)

    rng = random.Random(seed)
    sampled: Dict[str, List[str]] = {}
    for board, codes in by_board.items():
        shuffled = codes[:]  # copy to avoid mutating the local by_board lists
        rng.shuffle(shuffled)
        sampled[board] = shuffled[:per_board]

    all_codes = []
    for codes in sampled.values():
        all_codes.extend(codes)

    return {
        "seed": seed,
        "per_board": per_board,
        "boards": sampled,
        "all_codes": all_codes,
    }


# ----- Tidy 解析 -----

PERIOD_MAP = {
    "03-31": "Q1",
    "06-30": "half_year",
    "09-30": "Q3",
    "12-31": "annual",
}

EM_API_MAX_RETRIES = 3
EM_API_REQUEST_DELAY = 0.5  # seconds


def detect_period(report_date: str) -> Optional[str]:
    """Detect report period from date string like '2022-03-31' or '2022-03-31 00:00:00'.

    Returns 'Q1' / 'half_year' / 'Q3' / 'annual' or None if not a valid period end.
    """
    if not report_date or not isinstance(report_date, str):
        return None
    s = str(report_date).strip()
    # Strip time portion if present (e.g. "2022-03-31 00:00:00")
    if " " in s:
        s = s.split(" ")[0]
    m = re.search(r"(\d{2})-(\d{2})$", s)
    if not m:
        return None
    mm_dd = f"{m.group(1)}-{m.group(2)}"
    return PERIOD_MAP.get(mm_dd)


def parse_yi_value(val) -> Optional[float]:
    """Parse a financial value, handling '亿' suffix and commas.

    Examples:
        "100.50亿" -> 10050000000.0
        "1,234.56" -> 1234.56
        None -> None
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "false", "none"):
        return None
    try:
        if s.endswith("亿"):
            return float(s[:-1]) * 1e8
        s = s.replace(",", "")
        return float(s)
    except (ValueError, TypeError):
        return None


def parse_to_tidy(
    df: pd.DataFrame,
    stock_code: str,
    year: int,
    field_map: Dict[str, Tuple[str, int, str]],
    statement_type: str,
    source: str = "em",
) -> pd.DataFrame:
    """Parse EM raw DataFrame to Tidy CSV format."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=[
            "stock_code", "year", "period", "statement_type",
            "field_code", "field_name", "value", "display_order", "source",
        ])

    # Find date column (case-insensitive search for REPORT_DATE)
    date_col = None
    for c in df.columns:
        if str(c).upper() in ("REPORT_DATE", "报告日期"):
            date_col = c
            break
    if date_col is None:
        date_col = df.columns[0]

    rows = []
    for _, row in df.iterrows():
        report_date = str(row[date_col])
        if not report_date.startswith(str(year)):
            continue
        period = detect_period(report_date)
        if period is None:
            continue

        for col_name, (fcode, order, short_name) in field_map.items():
            if col_name not in df.columns:
                continue
            val = parse_yi_value(row[col_name])
            if val is None:
                continue
            rows.append({
                "stock_code": str(stock_code).zfill(6),
                "year": year,
                "period": period,
                "statement_type": statement_type,
                "field_code": fcode,
                "field_name": short_name,
                "value": val,
                "display_order": order,
                "source": source,
            })
    return pd.DataFrame(rows)


# ----- EM API 包装器 -----

def _em_api_call(api_func, symbol: str):
    """Single EM API call with retry. Returns DataFrame or None."""
    import akshare as ak
    func = getattr(ak, api_func)
    for attempt in range(EM_API_MAX_RETRIES):
        try:
            df = func(symbol=symbol)
            time.sleep(EM_API_REQUEST_DELAY)
            return df
        except Exception as e:
            print(f"  Retry {attempt + 1}/{EM_API_MAX_RETRIES} for {symbol}: {type(e).__name__}")
            time.sleep(2 ** attempt)
    return None


def _to_em_symbol(stock_code: str) -> str:
    """Convert 6-digit code to EM symbol (SH600519 / SZ000001)."""
    code = str(stock_code).zfill(6)
    if code.startswith(("600", "601", "603", "605", "688", "689")):
        return f"SH{code}"
    return f"SZ{code}"


def fetch_em_balance_sheet(stock_code: str):
    """Fetch balance sheet from AKShare EM API. Returns DataFrame or None."""
    return _em_api_call("stock_balance_sheet_by_report_em", _to_em_symbol(stock_code))


def fetch_em_income_statement(stock_code: str):
    """Fetch income statement from AKShare EM API. Returns DataFrame or None."""
    return _em_api_call("stock_profit_sheet_by_report_em", _to_em_symbol(stock_code))


def fetch_em_cash_flow(stock_code: str):
    """Fetch cash flow statement from AKShare EM API. Returns DataFrame or None."""
    return _em_api_call("stock_cash_flow_sheet_by_report_em", _to_em_symbol(stock_code))


# ----- EM 字段映射表加载 -----

_EM_COLUMN_MAPPINGS: Optional[Dict[str, Dict[str, Tuple[str, int, str]]]] = None


def load_field_map(statement_type: str) -> Dict[str, Tuple[str, int, str]]:
    """Load F-code field mapping for EM data.

    Uses the EM-specific English-column mapping file at data/em_column_mappings.json.
    Falls back to the legacy Chinese-name mapping if the file is not found.

    Args:
        statement_type: 'balance_sheet' / 'income_statement' / 'cash_flow'.

    Returns:
        {em_column_name: (F-code, display_order, short_name)}.
        Empty dict if not found.
    """
    global _EM_COLUMN_MAPPINGS
    if _EM_COLUMN_MAPPINGS is None:
        em_map_path = os.path.join(BASE_DIR, "data", "em_column_mappings.json")
        if os.path.exists(em_map_path):
            with open(em_map_path, "r", encoding="utf-8") as f:
                _EM_COLUMN_MAPPINGS = json.load(f)
        else:
            _EM_COLUMN_MAPPINGS = {}

    # Prefer EM-specific mapping (English column names)
    if _EM_COLUMN_MAPPINGS and statement_type in _EM_COLUMN_MAPPINGS:
        return _EM_COLUMN_MAPPINGS[statement_type]

    # Fallback: legacy decode_mappings_by_type.json (Chinese column names, Sina-style)
    decode_path = os.path.join(BASE_DIR, "data", "decode_mappings_by_type.json")
    if not os.path.exists(decode_path):
        return {}
    with open(decode_path, "r", encoding="utf-8") as f:
        all_maps = json.load(f)
    fcode_to_name = all_maps.get(statement_type, {})
    if not fcode_to_name:
        return {}
    # Load display_order from rules/
    rules_dir = os.path.join(BASE_DIR, "rules")
    fcode_to_order: Dict[str, int] = {}
    if os.path.isdir(rules_dir):
        for fname in os.listdir(rules_dir):
            if not (fname.endswith(".yaml") or fname.endswith(".yml")):
                continue
            try:
                import yaml
                with open(os.path.join(rules_dir, fname), "r", encoding="utf-8") as f:
                    rule = yaml.safe_load(f)
                if not rule or not isinstance(rule, dict):
                    continue
                # Actual format: {statement_type: {fcode: order_number}}
                # Look for the specific statement_type's mapping
                stmt_orders = rule.get(statement_type)
                if isinstance(stmt_orders, dict):
                    for fcode, order in stmt_orders.items():
                        if isinstance(order, (int, float)):
                            fcode_to_order[fcode] = int(order)
            except Exception:
                pass

    field_map: Dict[str, Tuple[str, int, str]] = {}
    for fcode, name in fcode_to_name.items():
        order = fcode_to_order.get(fcode, 999)
        field_map[name] = (fcode, order, name)
    return field_map


# ----- EM vs RDS 比对 -----

TOLERANCE_YUAN = 1.0
PERFECT_TOLERANCE_YUAN = 0.01


def compare_values(em_val: float, rds_val: float) -> Tuple[str, float]:
    """Compare two values using 1元 absolute tolerance.

    Returns:
        (severity, abs_diff)
        severity in {'perfect', 'good', 'anomaly'}
    """
    diff = abs(float(em_val) - float(rds_val))
    if diff <= PERFECT_TOLERANCE_YUAN:
        severity = "perfect"
    elif diff <= TOLERANCE_YUAN:
        severity = "good"
    else:
        severity = "anomaly"
    return severity, diff


def align_em_rds(em_data: dict, rds_data: dict) -> dict:
    """Align EM and RDS data by field_name (intersection)."""
    common = set(em_data.keys()) & set(rds_data.keys())
    return {
        f: {"em": em_data[f], "rds": rds_data[f]}
        for f in common
    }


def compare_em_rds_one_stock(
    em_data: dict,
    rds_data: dict,
    statement_type: str,
    stock_code: str,
    year: int,
    period: str,
) -> dict:
    """Compare EM data against RDS for one stock/period."""
    common = set(em_data.keys()) & set(rds_data.keys())
    aligned = align_em_rds(em_data, rds_data)

    matched = 0
    anomalies = []
    for field, vals in aligned.items():
        severity, diff = compare_values(vals["em"], vals["rds"])
        if severity in ("perfect", "good"):
            matched += 1
        else:
            anomalies.append({
                "field": field,
                "em": vals["em"],
                "rds": vals["rds"],
                "diff": diff,
            })

    total_common = len(common)
    total_em = len(em_data)
    total_rds = len(rds_data)
    missing_in_em = len(set(rds_data.keys()) - set(em_data.keys()))
    extra_in_em = len(set(em_data.keys()) - set(rds_data.keys()))

    return {
        "stock_code": stock_code,
        "year": year,
        "period": period,
        "statement_type": statement_type,
        "total_fields_em": total_em,
        "total_fields_rds": total_rds,
        "common_fields": total_common,
        "matched": matched,
        "unmatched": len(anomalies),
        "missing_in_em": missing_in_em,
        "extra_in_em": extra_in_em,
        "match_rate": matched / total_common if total_common else 0,
        "value_accuracy": matched / total_common if total_common else 0,
        "field_coverage": total_common / total_rds if total_rds else 0,
        "anomalies": anomalies,
    }


# ----- 完整性检查 -----

def check_completeness(sample: dict, output_root: str) -> dict:
    """Check download completeness for the sample.

    Args:
        sample: dict with 'all_codes' (and optionally 'boards').
        output_root: directory containing balance_sheet/, income_statement/, cash_flow/.

    Returns:
        {
          "total_stocks": int,
          "stocks_with_data": int,    # 至少有一张表
          "complete_stocks": int,     # 3 张表齐全
          "coverage_rate": float,     # with_data / total
          "completeness_rate": float, # complete / total
          "per_board": {board: {total, complete, with_data}},
          "per_statement": {stmt: count}
        }
    """
    STATEMENTS = ("balance_sheet", "income_statement", "cash_flow")
    all_codes = sample.get("all_codes", [])
    if "boards" in sample:
        boards = sample["boards"]
    else:
        boards = {"all": all_codes}

    total = len(all_codes)
    stocks_with_data = 0
    complete_stocks = 0
    per_board = {b: {"total": len(codes), "complete": 0, "with_data": 0} for b, codes in boards.items()}
    per_statement = {s: 0 for s in STATEMENTS}

    for code in all_codes:
        has_data = False
        all_three = True
        for stmt in STATEMENTS:
            csv_path = os.path.join(output_root, stmt, f"{code}.csv")
            if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                has_data = True
                per_statement[stmt] += 1
            else:
                all_three = False
        if has_data:
            stocks_with_data += 1
        if all_three:
            complete_stocks += 1

    for board, codes in boards.items():
        for code in codes:
            has_data = False
            all_three = True
            for stmt in STATEMENTS:
                csv_path = os.path.join(output_root, stmt, f"{code}.csv")
                if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                    has_data = True
                else:
                    all_three = False
            if has_data:
                per_board[board]["with_data"] += 1
            if all_three:
                per_board[board]["complete"] += 1

    return {
        "total_stocks": total,
        "stocks_with_data": stocks_with_data,
        "complete_stocks": complete_stocks,
        "coverage_rate": stocks_with_data / total if total else 0,
        "completeness_rate": complete_stocks / total if total else 0,
        "per_board": per_board,
        "per_statement": per_statement,
    }


# ----- EM tidy CSV 加载 -----

def load_em_tidy(stock_code: str, statement_type: str, year: int, period: str, output_root: str) -> dict:
    """Load EM tidy CSV and pivot to {field_name: value}."""
    path = os.path.join(output_root, statement_type, f"{stock_code}.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"stock_code": str})
    df = df[(df["year"] == year) & (df["period"] == period)]
    return dict(zip(df["field_name"], df["value"]))


# ----- EM vs RDS 批量比对 -----

def compare_em_rds_batch(
    sample: dict,
    rds_loader,
    output_root: str,
    year: int = 2022,
    periods: Tuple[str, ...] = ("Q1", "half_year", "Q3", "annual"),
) -> dict:
    """Batch compare EM vs RDS for sample stocks across all periods and statements.

    Args:
        sample: dict with 'all_codes' and 'boards'.
        rds_loader: RdsLoader instance.
        output_root: EM data root.
        year: target year.
        periods: tuple of periods to compare.

    Returns:
        {
            "summary": {total_comparisons, total_matched, total_unmatched, ...},
            "per_stock": [compare_em_rds_one_stock result],
            "per_statement": {stmt: stats},
            "per_board": {board: stats},
        }
    """
    STATEMENTS = ("balance_sheet", "income_statement", "cash_flow")
    all_results = []
    per_statement = {s: {"matched": 0, "unmatched": 0, "common": 0} for s in STATEMENTS}
    per_board = {}

    for board, codes in sample.get("boards", {}).items():
        per_board[board] = {"matched": 0, "unmatched": 0, "common": 0, "stocks": 0}

    for stock_code in sample["all_codes"]:
        for stmt_type in STATEMENTS:
            for period in periods:
                em_data = load_em_tidy(stock_code, stmt_type, year, period, output_root)
                if not em_data:
                    continue
                rds_data = rds_loader.load_stock_data(stock_code, year, stmt_type)
                if not rds_data:
                    continue
                result = compare_em_rds_one_stock(
                    em_data, rds_data, stmt_type, stock_code, year, period,
                )
                all_results.append(result)
                per_statement[stmt_type]["matched"] += result["matched"]
                per_statement[stmt_type]["unmatched"] += result["unmatched"]
                per_statement[stmt_type]["common"] += result["common_fields"]

    for stock_code in sample["all_codes"]:
        board = "unknown"
        for b, codes in sample.get("boards", {}).items():
            if stock_code in codes:
                board = b
                break
        for r in all_results:
            if r["stock_code"] == stock_code:
                per_board[board]["matched"] += r["matched"]
                per_board[board]["unmatched"] += r["unmatched"]
                per_board[board]["common"] += r["common_fields"]
                per_board[board]["stocks"] += 1
                break

    total_matched = sum(per_statement[s]["matched"] for s in STATEMENTS)
    total_unmatched = sum(per_statement[s]["unmatched"] for s in STATEMENTS)
    total_common = sum(per_statement[s]["common"] for s in STATEMENTS)
    total_comparisons = len(all_results)

    return {
        "summary": {
            "total_comparisons": total_comparisons,
            "total_matched": total_matched,
            "total_unmatched": total_unmatched,
            "total_common_fields": total_common,
            "overall_match_rate": total_matched / total_common if total_common else 0,
        },
        "per_statement": per_statement,
        "per_board": per_board,
        "per_stock": all_results,
    }