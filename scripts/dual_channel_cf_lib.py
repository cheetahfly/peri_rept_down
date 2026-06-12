# -*- coding: utf-8 -*-
"""
Dual-channel CF 对比工具库：在两渠道数值字典之间找最佳匹配并分类差异。

辅助 tri_channel_cf_lib 使用（tri_match 复用本模块的 best_match/classify_diff）。
"""
from typing import Dict, Tuple, Optional


# 差异分级阈值（相对误差 %）
EXACT_MAX = 0.01      # 视为完全相等
CLOSE_MAX = 1.0       # 视为接近
WARN_MAX = 10.0       # 警告
ANOMALY_MAX = 50.0    # 异常
# > ANOMALY_MAX 视为 no_match（数值完全不在合理范围内）

CLASS_COLORS = {
    "exact":     "#2ecc71",  # 绿
    "close":     "#f1c40f",  # 黄
    "warn":      "#e67e22",  # 橙
    "anomaly":   "#e74c3c",  # 红
    "no_match":  "#95a5a6",  # 灰
}


def best_match(target: float, candidates: Dict[str, float]) -> Tuple[Optional[str], Optional[float], Optional[float], Optional[float]]:
    """在 candidates 中找与 target 值最接近的项。

    返回 (label, value, abs_diff, rel_err_pct)。
    若 candidates 为空，返回 (None, None, None, None)。
    """
    if not candidates:
        return None, None, None, None
    best_label = None
    best_val = None
    best_abs = None
    for label, val in candidates.items():
        if val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        abs_diff = abs(v - target)
        if best_abs is None or abs_diff < best_abs:
            best_abs = abs_diff
            best_label = label
            best_val = v
    if best_label is None:
        return None, None, None, None
    rel_err_pct = (best_abs / abs(target) * 100.0) if target else None
    return best_label, best_val, best_abs, rel_err_pct


def classify_diff(abs_diff: Optional[float], rel_err_pct: Optional[float]) -> Tuple[str, str]:
    """根据 (abs_diff, rel_err_pct) 返回 (class, color)。"""
    if abs_diff is None or rel_err_pct is None:
        return "no_match", CLASS_COLORS["no_match"]
    if abs_diff < 0.01 or rel_err_pct < EXACT_MAX:
        return "exact", CLASS_COLORS["exact"]
    if rel_err_pct < CLOSE_MAX:
        return "close", CLASS_COLORS["close"]
    if rel_err_pct < WARN_MAX:
        return "warn", CLASS_COLORS["warn"]
    if rel_err_pct < ANOMALY_MAX:
        return "anomaly", CLASS_COLORS["anomaly"]
    return "no_match", CLASS_COLORS["no_match"]
