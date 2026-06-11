# -*- coding: utf-8 -*-
"""
PDF 提取质量回归测试。

基线（2026-06-11 Job 1 结束时实测）：
- 600519 已达计划 ≥95% 目标
- 其他 6 只受 PDF↔RDS schema 真实差异限制（项目合并/拆分），未达 95%
- 用户接受当前基线，待后续阶段提升

测试以"不退化"为目标：每只股票 exact_rate 不得低于当前基线 -1pp。
"""
import json
import os
import pytest

EVAL_SUMMARY = "tmp/eval_pdf_extraction_2020/_eval_summary.json"

# Per-stock baseline（2026-06-11 实测值，留 1pp 容差）
EXPECTED_BASELINE = {
    "600519": 94.0,  # 95.92
    "002415": 79.0,  # 80.36
    "600887": 79.0,  # 80.0
    "300750": 68.0,  # 69.09
    "000858": 67.0,  # 68.18
    "002475": 61.0,  # 62.96
    "000002": 60.0,  # 61.11
}


def load_eval():
    if not os.path.exists(EVAL_SUMMARY):
        pytest.skip(f"eval summary not generated; run scripts/eval_pdf_extraction.py first")
    with open(EVAL_SUMMARY, "r", encoding="utf-8") as f:
        return {r["stock_code"]: r for r in json.load(f) if r.get("status") == "OK"}


@pytest.mark.parametrize("stock_code,min_rate", list(EXPECTED_BASELINE.items()))
def test_extraction_meets_baseline(stock_code, min_rate):
    results = load_eval()
    if stock_code not in results:
        pytest.skip(f"{stock_code} not in eval results")
    actual = results[stock_code]["exact_rate"]
    assert actual >= min_rate, (
        f"{stock_code} exact_rate dropped: {actual}% < baseline {min_rate}%"
    )


def test_all_7_stocks_present():
    """守护：确保 7 只测试股票都出现在 eval 中"""
    results = load_eval()
    expected = set(EXPECTED_BASELINE.keys())
    actual = set(results.keys())
    missing = expected - actual
    assert not missing, f"missing stocks in eval: {missing}"


def test_no_55x_placeholder_in_extracted():
    """守护：确保 footnote sentinel bug (-55x) 不再泄露到数据"""
    results = load_eval()
    leaks = []
    for stock_code, r in results.items():
        for d in r.get("details", []):
            pv = d.get("pdf_value")
            if isinstance(pv, (int, float)) and -570 < pv < -540:
                leaks.append(f"{stock_code} {d['rds_name']!r} → {pv}")
    assert not leaks, f"footnote sentinel leaked: {leaks}"
