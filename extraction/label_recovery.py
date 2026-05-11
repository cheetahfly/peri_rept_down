# -*- coding: utf-8 -*-
"""
Label recovery for CID-font garbled PDFs.

Recovers financial item labels (e.g. 经营活动产生的现金流量净额)
from position-based keys (e.g. p161_r1_c1) using y-position matching
against reference PDFs or standard financial statement templates.
"""
from typing import Dict, List, Optional, Tuple

# =============================================================================
# Standard Financial Statement Templates (证监会格式)
# =============================================================================

BS_TEMPLATE = [
    "流动资产合计",          # 0
    "非流动资产合计",        # 1
    "资产总计",              # 2
    "流动负债合计",          # 3
    "非流动负债合计",        # 4
    "负债合计",              # 5
    "所有者权益合计",        # 6
    "负债和所有者权益总计",  # 7
]

IS_TEMPLATE = [
    "营业收入",              # 0
    "营业成本",              # 1
    "销售费用",              # 2
    "管理费用",              # 3
    "研发费用",              # 4
    "财务费用",              # 5
    "资产减值损失",          # 6
    "公允价值变动收益",      # 7
    "投资收益",              # 8
    "营业利润",              # 9
    "营业外收入",            # 10
    "营业外支出",            # 11
    "利润总额",              # 12
    "所得税费用",            # 13
    "净利润",                # 14
    "归属于母公司所有者的净利润",  # 15
]

CF_TEMPLATE = [
    "一、经营活动产生的现金流量净额",     # 0
    "其中：取得投资收益收到的现金",      # 1
    "处置固定资产、无形资产收回的现金净额", # 2
    "处置子公司收到的现金净额",          # 3
    "收到其他与经营活动有关的现金",     # 4
    "经营活动现金流出小计",             # 5
    "经营活动产生的现金流量净额",        # 6
    "二、投资活动产生的现金流量净额",     # 7
    "其中：收回投资收到的现金",          # 8
    "取得投资收益收到的现金",            # 9
    "处置固定资产、无形资产支付的现金",  # 10
    "购建固定资产、无形资产支付的现金",  # 11
    "投资支付的现金",                    # 12
    "投资活动现金流出小计",             # 13
    "投资活动产生的现金流量净额",        # 14
    "三、筹资活动产生的现金流量净额",     # 15
    "其中：吸收投资收到的现金",          # 16
    "取得借款收到的现金",                # 17
    "发行债券收到的现金",               # 18
    "筹资活动现金流入小计",             # 19
    "偿还债务支付的现金",               # 20
    "分配股利、利润或偿付利息支付的现金", # 21
    "筹资活动现金流出小计",             # 22
    "筹资活动产生的现金流量净额",        # 23
    "四、汇率变动对现金的影响",         # 24
    "五、现金及现金等价物净增加额",     # 25
    "加：期初现金及现金等价物余额",     # 26
    "六、期末现金及现金等价物余额",     # 27
]

TEMPLATE_MAP = {
    "balance_sheet": BS_TEMPLATE,
    "income_statement": IS_TEMPLATE,
    "cash_flow": CF_TEMPLATE,
}


def _load_template(statement_type: str) -> List[str]:
    """Return standard template item list for the statement type."""
    return TEMPLATE_MAP.get(statement_type, [])


# =============================================================================
# Constants
# =============================================================================

Y_TOLERANCE = 15.0          # max y-distance (points) for reference row matching
MIN_PRIMARY_VALUE = 1000.0  # minimum |value| for primary item label


# =============================================================================
# Core Label Recovery
# =============================================================================

def recover_labels(
    recovered_data: Dict,
    reference_data: Optional[Dict] = None,
    statement_type: Optional[str] = None,
) -> Dict:
    """
    Recover financial item labels from position-based keys.

    Args:
        recovered_data: output from recover_statement() with position-keyed flat_data
        reference_data: successfully extracted data of same company/year, or None
        statement_type: "balance_sheet" | "income_statement" | "cash_flow"

    Returns:
        {
            "flat_data": {"经营活动产生的现金流量净额": 285449.0, ...},
            "label_map": [{"original_key": "p0_r0_c0", "label": "...", ...}],
            "confidence": 0.85,
            "match_method": "reference" | "template" | "none",
        }
    """
    flat_data = recovered_data.get("data", {})
    page_data = recovered_data.get("page_data", {})

    # Collect all rows with y_positions from recovered data
    recovered_rows = []
    for page_str, page_info in page_data.items():
        page_idx = int(page_str) if page_str.isdigit() else 0
        for row_info in page_info.get("rows", []):
            row_info_copy = dict(row_info)
            row_info_copy["page"] = page_idx
            recovered_rows.append(row_info_copy)

    label_map: List[Dict] = []
    labeled_flat: Dict = {}
    total_confidence = 0.0
    match_method = "none"

    # Layer 1: Try reference PDF matching (highest priority)
    if reference_data is not None:
        ref_page_data = reference_data.get("page_data", {})
        ref_rows = []
        for page_str, page_info in ref_page_data.items():
            for row_info in page_info.get("rows", []):
                row_info_copy = dict(row_info)
                row_info_copy["page"] = int(page_str) if page_str.isdigit() else 0
                # Find label from reference flat_data
                ref_flat = reference_data.get("data", {})
                for lbl, val in ref_flat.items():
                    if isinstance(val, (int, float)) and val in row_info.get("values", []):
                        row_info_copy["label"] = lbl
                        break
                ref_rows.append(row_info_copy)

        if ref_rows and recovered_rows:
            ref_matches = _match_by_y_position(recovered_rows, ref_rows, y_tolerance=Y_TOLERANCE)
            if ref_matches:
                match_method = "reference"
                for (page_idx, row_idx, col_idx), (label, conf) in ref_matches.items():
                    key = f"p{page_idx}_r{row_idx}_c{col_idx}"
                    if key in flat_data:
                        val = flat_data[key]
                        labeled_flat[label] = val
                        is_primary = abs(val) >= MIN_PRIMARY_VALUE
                        label_map.append({
                            "original_key": key,
                            "label": label,
                            "value": val,
                            "is_primary": is_primary,
                            "confidence": conf,
                        })

    # Layer 2: Template matching (fill in remaining keys or fallback)
    if statement_type and not labeled_flat:
        template = _load_template(statement_type)
        for page_str, page_info in page_data.items():
            page_idx = int(page_str) if page_str.isdigit() else 0
            for row_info in page_info.get("rows", []):
                row_idx = row_info["row"]
                values = row_info["values"]
                label = template[row_idx] if row_idx < len(template) else f"行{row_idx}"
                for col_idx, val in enumerate(values):
                    if val is None:
                        continue
                    key = f"p{page_idx}_r{row_idx}_c{col_idx}"
                    if key not in labeled_flat:
                        labeled_flat[label] = val
                        is_primary = abs(val) >= MIN_PRIMARY_VALUE
                        label_map.append({
                            "original_key": key,
                            "label": label,
                            "value": val,
                            "is_primary": is_primary,
                            "confidence": 0.7,
                        })
        if labeled_flat and match_method == "none":
            match_method = "template"

    # Graceful degradation: if nothing matched, keep original position keys
    if not labeled_flat:
        labeled_flat = flat_data
        match_method = "none"
        total_confidence = 0.0
    else:
        total_confidence = sum(e["confidence"] for e in label_map) / len(label_map) if label_map else 0.0

    return {
        "flat_data": labeled_flat,
        "label_map": label_map,
        "confidence": total_confidence,
        "match_method": match_method,
    }


def _match_by_y_position(
    recovered_rows: List[Dict],
    reference_rows: List[Dict],
    y_tolerance: float = 15.0,
) -> Dict:
    """
    Match recovered rows to reference rows by y-position.

    Args:
        recovered_rows: list of {"row": int, "values": [float], "y_position": float, "page": int}
        reference_rows: list of {"row": int, "values": [float], "y_position": float, "page": int, "label": str}
        y_tolerance: max y-distance for a match (points)

    Returns:
        Dict mapping (page_idx, row_idx, col_idx) → (label, confidence=1.0)
    """
    matches: Dict = {}
    for rec_row in recovered_rows:
        rec_y = rec_row.get("y_position", 0.0)
        rec_row_idx = rec_row["row"]
        best_label = None
        best_dist = float("inf")

        for ref_row in reference_rows:
            ref_y = ref_row.get("y_position", 0.0)
            dist = abs(rec_y - ref_y)
            if dist <= y_tolerance and dist < best_dist:
                best_dist = dist
                best_label = ref_row.get("label")

        if best_label:
            for col_idx, val in enumerate(rec_row.get("values", [])):
                if val is not None:
                    key = (rec_row.get("page", 0), rec_row_idx, col_idx)
                    matches[key] = (best_label, 1.0)

    return matches
