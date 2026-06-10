#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M6: Aggregate all evaluation outputs into a structured Markdown report.

Usage:
    python scripts/eval_em_report.py

Output:
    docs/audit/2026-06-10-em-channel-evaluation.md
"""
import json
import os
import sys
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import build_conclusion  # noqa: E402

BASE = _PROJECT_ROOT
OUTPUT_ROOT = os.path.join(BASE, "data", "exports_v2", "em_evaluation")
SAMPLE_PATH = os.path.join(OUTPUT_ROOT, "sample_200.json")
COMPLETE_PATH = os.path.join(OUTPUT_ROOT, "completeness.json")
COMPARE_PATH = os.path.join(OUTPUT_ROOT, "compare_rds_report.json")
HISTORICAL_PATH = os.path.join(OUTPUT_ROOT, "historical_issues.json")
REPORT_PATH = os.path.join(BASE, "docs", "audit", "2026-06-10-em-channel-evaluation.md")


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_report(sample: dict, completeness: dict, compare: dict, historical: dict) -> str:
    """Render the final Markdown report."""
    conclusion = build_conclusion(completeness, compare, historical)
    cov = completeness.get("coverage_rate", 0)
    comp_rate = completeness.get("completeness_rate", 0)
    s = compare.get("summary", {})
    overall_match = s.get("overall_match_rate", 0)
    total_matched = s.get("total_matched", 0)
    total_common = s.get("total_common_fields", 0)
    h = historical

    per_board_rows = []
    for board, stats in completeness.get("per_board", {}).items():
        per_board_rows.append(
            f"| {board} | {stats['total']} | {stats['with_data']} | {stats['complete']} |"
        )
    per_board_table = "\n".join(per_board_rows) if per_board_rows else "| (无) | - | - | - |"

    per_stmt_rows = []
    for stmt, stats in compare.get("per_statement", {}).items():
        rate = stats["matched"] / stats["common"] * 100 if stats["common"] else 0
        per_stmt_rows.append(
            f"| {stmt} | {stats['matched']} | {stats['common']} | {rate:.2f}% |"
        )
    per_stmt_table = "\n".join(per_stmt_rows) if per_stmt_rows else "| (无) | - | - | - |"

    md = f"""# EM 渠道全面评估结论

**日期**: {datetime.now().strftime('%Y-%m-%d')}
**评估范围**: akshare-EM（东方财富）渠道对 A 股 2022 年 Q1/半年报/Q3/年报 × 资产负债表/利润表/现金流量表

## 1. 抽样覆盖性

- **总样本**: 200 只（沪市主板 {len(sample.get('boards', {}).get('sh_main', []))} / 深市主板 {len(sample.get('boards', {}).get('sz_main', []))} / 创业板 {len(sample.get('boards', {}).get('chinext', []))} / 科创板 {len(sample.get('boards', {}).get('star', []))}）
- **覆盖率**: {completeness.get('stocks_with_data', 0)}/200 = **{cov * 100:.2f}%**
- **完整率**: {completeness.get('complete_stocks', 0)}/200 = **{comp_rate * 100:.2f}%**

### 分板块

| 板块 | 总数 | 有数据 | 三表齐全 |
|------|------|--------|----------|
{per_board_table}

### 分表

| 报表 | 有数据的股票数 |
|------|----------------|
"""
    for stmt, count in completeness.get("per_statement", {}).items():
        md += f"| {stmt} | {count} |\n"

    md += f"""
## 2. 数据质量（vs RDS）

- **比对样本数**: {s.get('total_comparisons', 0)} (股票×期次×报表)
- **字段匹配率**: {total_matched}/{total_common} = **{overall_match * 100:.2f}%**（差值 ≤ 1 元）

### 分表

| 报表 | 匹配字段 | 总字段 | 匹配率 |
|------|----------|--------|--------|
{per_stmt_table}

## 3. 历史疑难数据 EM 重测

- **疑难样本数**: {h.get('anomalies_count', 0)}（sina 与 RDS 差值 > 1 元的字段）
- **EM 匹配数**: {h.get('em_matched', 0)}
- **EM 仍不匹配**: {h.get('em_unmatched', 0)}
- **EM 无数据**: {h.get('em_no_data', 0)}
- **EM 改善率**: **{h.get('improvement', 0) * 100:.2f}%**（vs sina 0% 匹配）

## 4. 最终结论

**{conclusion['text']}**

| 指标 | 实际值 | 阈值（main） | 阈值（assist） |
|------|--------|---------------|-----------------|
| 覆盖率 | {cov * 100:.2f}% | ≥ 95% | ≥ 70% |
| 字段匹配率 | {overall_match * 100:.2f}% | ≥ 95% | ≥ 70% |
| EM 改善率 | {h.get('improvement', 0) * 100:.2f}% | - | - |

## 5. 建议

- 数据文件: `data/exports_v2/em_evaluation/`
- 比对报告: `data/exports_v2/em_evaluation/compare_rds_report.json`
- 疑难重测: `data/exports_v2/em_evaluation/historical_issues.json`

## 6. 已知局限

- EM 渠道**不提供间接法 CF**（与 sina 一致），间接法 CF 仍需从 PDF 年报提取或使用其他渠道
- 抽样固定 seed=42，结果可重现但不一定是全市场最优代表
- 评估仅覆盖 2022 年，2023+ 数据未测试

---
*报告由 `scripts/eval_em_report.py` 自动生成*
"""
    return md


def main() -> int:
    sample = load_json(SAMPLE_PATH)
    completeness = load_json(COMPLETE_PATH)
    compare = load_json(COMPARE_PATH)
    historical = load_json(HISTORICAL_PATH)

    if not all([sample, completeness, compare, historical]):
        print("ERROR: Some input files missing. Run previous steps first.")
        print(f"  sample: {SAMPLE_PATH} -> exists={os.path.exists(SAMPLE_PATH)}")
        print(f"  completeness: {COMPLETE_PATH} -> exists={os.path.exists(COMPLETE_PATH)}")
        print(f"  compare: {COMPARE_PATH} -> exists={os.path.exists(COMPARE_PATH)}")
        print(f"  historical: {HISTORICAL_PATH} -> exists={os.path.exists(HISTORICAL_PATH)}")
        return 1

    md = render_report(sample, completeness, compare, historical)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Report saved to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())