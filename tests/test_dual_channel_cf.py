# -*- coding: utf-8 -*-
"""
Unit tests for scripts/dual_channel_cf_lib.py。
基于 tmp/akshare_test_600519_2020/ 中已有的 fixture CSV。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from dual_channel_cf_lib import (  # noqa: E402
    extract_em_year_values,
    extract_ths_new_year_values,
    dual_match,
    classify_diff,
)

TEST_DATA = "tmp/akshare_test_600519_2020"


def test_extract_em_year_600519_2020():
    csv_path = os.path.join(TEST_DATA, "raw_01_em_yearly.csv")
    values = extract_em_year_values(csv_path, 2020)
    # 600519 2020 应有约 51 个非空字段
    assert len(values) >= 50, f"expected >=50, got {len(values)}"
    # 销售商品 = 107,024,384,560.17
    assert any(abs(v - 107024384560.17) < 0.5 for v in values.values()), \
        "expected 销售商品 107,024,384,560.17 not found"


def test_extract_em_year_wrong_year_returns_empty():
    csv_path = os.path.join(TEST_DATA, "raw_01_em_yearly.csv")
    values = extract_em_year_values(csv_path, 1995)
    assert values == {}


def test_extract_ths_new_year_600519_2020():
    csv_path = os.path.join(TEST_DATA, "raw_09_ths_new_yearly.csv")
    values = extract_ths_new_year_values(csv_path, 2020)
    assert len(values) >= 40
    # 净利润 = 49,523,329,882.40
    assert any(abs(v - 49523329882.40) < 0.5 for v in values.values()), \
        "expected 净利润 49,523,329,882.40 not found"


def test_classify_diff_exact():
    cls, color = classify_diff(0.005, 0)
    assert cls == "exact" and color == "green"


def test_classify_diff_sub_yuan():
    cls, color = classify_diff(0.5, 0)
    assert cls == "sub_yuan" and color == "yellow"


def test_classify_diff_rounded():
    cls, color = classify_diff(50, 0.0001)
    assert cls == "rounded" and color == "orange"


def test_classify_diff_large_error():
    cls, color = classify_diff(1_000_000, 5.0)
    assert cls == "large_error" and color == "red"


def test_classify_diff_no_match():
    cls, color = classify_diff(None, None)
    assert cls == "no_match" and color == "gray"


def test_dual_match_600519():
    em_csv = os.path.join(TEST_DATA, "raw_01_em_yearly.csv")
    ths_csv = os.path.join(TEST_DATA, "raw_09_ths_new_yearly.csv")
    em = extract_em_year_values(em_csv, 2020)
    ths = extract_ths_new_year_values(ths_csv, 2020)
    rows = dual_match(em, ths)
    assert len(rows) == len(em)
    exact_count = sum(1 for r in rows if r["class"] == "exact")
    # 600519 EM vs THS new 期望 ≥35 exact（smoke test 实测 49）
    assert exact_count >= 35, f"expected >=35 exact, got {exact_count}"
