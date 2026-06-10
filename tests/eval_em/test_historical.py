"""Tests for historical sina vs RDS scanner."""
import os
import pandas as pd
import pytest

from scripts.eval_em_lib import scan_sina_anomalies


def test_scan_sina_anomalies_finds_diff(tmp_path):
    """差值 > 1 元的字段应被标记为异常。"""
    sina_csv = tmp_path / "sina.csv"
    df = pd.DataFrame({
        "stock_code": ["600000", "600000", "600001"],
        "year": [2022, 2022, 2022],
        "period": ["annual", "annual", "annual"],
        "statement_type": ["balance_sheet", "balance_sheet", "balance_sheet"],
        "field_name": ["货币资金", "应收账款", "货币资金"],
        "value": [100.0, 50.5, 100.0],
    })
    df.to_csv(sina_csv, index=False, encoding="utf-8-sig")

    rds_data_map = {
        ("600000", 2022, "balance_sheet"): {"货币资金": 100.0, "应收账款": 100.0},  # 应收账款差 49.5
        ("600001", 2022, "balance_sheet"): {"货币资金": 100.0},
    }

    def fake_rds_loader(code, year, stmt):
        return rds_data_map.get((code, year, stmt), {})

    anomalies = scan_sina_anomalies(str(sina_csv), fake_rds_loader, tolerance=1.0)

    assert len(anomalies) == 1
    assert anomalies[0]["stock_code"] == "600000"
    assert anomalies[0]["field_name"] == "应收账款"
    assert abs(anomalies[0]["diff"] - 49.5) < 0.01


def test_scan_sina_anomalies_no_diff(tmp_path):
    """全部匹配 → 0 异常。"""
    sina_csv = tmp_path / "sina.csv"
    df = pd.DataFrame({
        "stock_code": ["600000"],
        "year": [2022],
        "period": ["annual"],
        "statement_type": ["balance_sheet"],
        "field_name": ["货币资金"],
        "value": [100.0],
    })
    df.to_csv(sina_csv, index=False, encoding="utf-8-sig")

    def fake_rds_loader(code, year, stmt):
        return {"货币资金": 100.0}

    anomalies = scan_sina_anomalies(str(sina_csv), fake_rds_loader, tolerance=1.0)
    assert len(anomalies) == 0


def test_scan_sina_anomalies_tolerance(tmp_path):
    """差值 0.5 元（≤ 1元）→ 不算异常。"""
    sina_csv = tmp_path / "sina.csv"
    df = pd.DataFrame({
        "stock_code": ["600000"],
        "year": [2022],
        "period": ["annual"],
        "statement_type": ["balance_sheet"],
        "field_name": ["货币资金"],
        "value": [100.5],
    })
    df.to_csv(sina_csv, index=False, encoding="utf-8-sig")

    def fake_rds_loader(code, year, stmt):
        return {"货币资金": 100.0}

    anomalies = scan_sina_anomalies(str(sina_csv), fake_rds_loader, tolerance=1.0)
    assert len(anomalies) == 0