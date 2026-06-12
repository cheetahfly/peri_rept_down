# -*- coding: utf-8 -*-
"""
EM + THS new 双渠道现金流量表对比工具库。

注意：复用 scripts/akshare_cf_test_compare.py 中的 normalize_value/best_match，
但 extract_* 函数需要参数化年份（原版写死 2020）。
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from akshare_cf_test_compare import normalize_value, best_match  # noqa: E402

# EM 排除列（元数据 + YoY）
EM_EXCLUDE = {
    "SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "ORG_CODE", "ORG_TYPE",
    "REPORT_DATE", "REPORT_TYPE", "REPORT_DATE_NAME", "SECURITY_TYPE_CODE",
    "NOTICE_DATE", "UPDATE_DATE", "CURRENCY", "LISTING_STATE", "OPINION_TYPE",
    "OPDATE", "OSOPINION_TYPE",
}


def extract_em_year_values(csv_path, year):
    """EM CSV → {col_name_en: value}，提取指定年份年报（REPORT_DATE 以 'YYYY-12-31' 开头）"""
    df = pd.read_csv(csv_path)
    df["REPORT_DATE"] = df["REPORT_DATE"].astype(str)
    mask = df["REPORT_DATE"].str.startswith(f"{year}-12-31")
    if mask.sum() == 0:
        return {}
    r = df[mask].iloc[0].to_dict()
    out = {}
    for c, v in r.items():
        if c in EM_EXCLUDE or c.endswith("_YOY"):
            continue
        nv = normalize_value(v)
        if nv is not None:
            out[c] = nv
    return out


def extract_ths_new_year_values(csv_path, year):
    """THS new 长格式 CSV → {metric_name: value}，按 report_date 年份过滤"""
    df = pd.read_csv(csv_path)
    df["report_date"] = df["report_date"].astype(str)
    mask = df["report_date"].str.startswith(f"{year}-12-31")
    sub = df[mask]
    out = {}
    for _, row in sub.iterrows():
        name = row.get("metric_name")
        nv = normalize_value(row.get("value"))
        if name and nv is not None:
            out[str(name)] = nv
    return out


def classify_diff(diff, rel_err):
    """返回 (class, color_hint)；class 描述渠道间差异级别"""
    if diff is None:
        return ("no_match", "gray")
    if diff < 0.01:
        return ("exact", "green")
    if diff < 1.0:
        return ("sub_yuan", "yellow")
    if rel_err is not None and rel_err < 1.0:
        return ("rounded", "orange")
    return ("large_error", "red")


def dual_match(em_values, ths_values):
    """对每个 EM 字段在 THS 中找最佳匹配，返回对照清单。

    返回 list of:
      {em_field, em_value, ths_label, ths_value, abs_diff, rel_err_pct, class, color}
    """
    rows = []
    for em_field, em_v in em_values.items():
        ths_label, ths_v, diff, rel = best_match(em_v, ths_values)
        cls, color = classify_diff(diff, rel)
        rows.append({
            "em_field": em_field, "em_value": em_v,
            "ths_label": ths_label, "ths_value": ths_v,
            "abs_diff": diff, "rel_err_pct": rel,
            "class": cls, "color": color,
        })
    return rows
