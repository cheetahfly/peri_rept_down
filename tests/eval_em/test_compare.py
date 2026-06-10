"""Tests for EM vs RDS comparison logic."""
import pytest

from scripts.eval_em_lib import (
    compare_values,
    TOLERANCE_YUAN,
    PERFECT_TOLERANCE_YUAN,
    align_em_rds,
    compare_em_rds_one_stock,
)


# ---- Tolerance constants ----

def test_tolerance_constants():
    """1元容差必须与项目分精度规则一致。"""
    assert TOLERANCE_YUAN == 1.0
    assert PERFECT_TOLERANCE_YUAN == 0.01


# ---- compare_values ----

def test_compare_values_within_tolerance():
    """差值 ≤ 1.00 元 = match。"""
    severity, diff = compare_values(100.0, 100.5)
    assert severity == "good"
    assert diff == 0.5


def test_compare_values_perfect():
    """差值 ≤ 0.01 元 = perfect。"""
    severity, diff = compare_values(100.0, 100.0)
    assert severity == "perfect"
    assert diff == 0.0


def test_compare_values_exceeds_tolerance():
    """差值 > 1.00 元 = anomaly。"""
    severity, diff = compare_values(100.0, 102.0)
    assert severity == "anomaly"
    assert diff == 2.0


def test_compare_values_negative_diff():
    """绝对值差，无视正负。"""
    severity, diff = compare_values(100.0, 99.0)
    assert severity == "good"
    assert diff == 1.0


# ---- align_em_rds ----

def test_align_em_rds_by_field_name():
    """EM 和 RDS 都用 field_name 作为 key 对齐。"""
    em = {"货币资金": 100.0, "应收账款": 50.0, "EM独有字段": 30.0}
    rds = {"货币资金": 100.5, "应收账款": 60.0, "RDS独有字段": 20.0}
    aligned = align_em_rds(em, rds)
    assert set(aligned.keys()) == {"货币资金", "应收账款"}
    assert aligned["货币资金"]["em"] == 100.0
    assert aligned["货币资金"]["rds"] == 100.5


# ---- compare_em_rds_one_stock ----

def test_compare_em_rds_full_match():
    em = {"货币资金": 100.0, "应收账款": 50.0}
    rds = {"货币资金": 100.0, "应收账款": 50.0, "RDS独有": 200.0}
    result = compare_em_rds_one_stock(em, rds, "balance_sheet", "600000", 2022, "annual")
    assert result["matched"] == 2
    assert result["unmatched"] == 0
    assert result["missing_in_em"] == 1
    assert result["match_rate"] == 1.0


def test_compare_em_rds_partial_match():
    em = {"货币资金": 100.0, "应收账款": 50.0}
    rds = {"货币资金": 100.0, "应收账款": 100.0}  # 应收账款差 50 元
    result = compare_em_rds_one_stock(em, rds, "balance_sheet", "600000", 2022, "annual")
    assert result["matched"] == 1
    assert result["unmatched"] == 1
    assert result["match_rate"] == 0.5