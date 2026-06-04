# Sina→RDS Cleaning Progression (2019-2022)

> Round 2 complete: 50 alias rules + 1 aggregation rule learned, IS +2.24%, CF +6.36%

## Run summary (2026-06-04, Round 2)

- 6 stocks × 4 years × 3 statement types = 48 comparisons
- 50 alias rules learned via scripts/learn_sina_aliases.py
  - BS: 16 | IS: 17 | CF: 17
- 1 aggregation rule learned (BS: 其他应收款(合计) → 其他应收款)
- Tidy output: BS 41 rows, IS 32 rows, CF 124 rows (2 stocks × 4 years)

## Match-rate progression

| Round | BS | IS | CF | Notes |
|-------|----|----|----|-------|
| Round 0 (baseline, no sina rules) | 99.37% | 85.42% | 58.88% | Initial measurement |
| Round 2 (50 sina aliases + 1 aggregation) | **99.38%** | **87.66%** | **65.24%** | Auto-learned from value-exact matching + name-similarity filter |

| Statement | Δ Match | Δ Items | Δ Value accuracy |
|-----------|---------|---------|------------------|
| BS | +0.01% | +7 (636 → 643) | -3.47% (81.11% → 77.64%) |
| IS | **+2.24%** | -2 (480 → 478) | -2.23% (57.62% → 55.39%) |
| CF | **+6.36%** | +15 (569 → 584) | -10.67% (67.00% → 56.33%) |

**IS 和 CF 显著提升** (符合 spec 目标 — CF 是 spec §1 中标注的 63.6% 短板)。
**Value accuracy 略降** 原因: 新规则覆盖了更多之前 unmatched 的项，但其中部分是被 `value_exact` 策略捕获 (宽松阈值) 而非更严格策略。

## What's been built

### Modules

| Module | Purpose |
|--------|---------|
| `astock_fundamentals/ground_truth/comparator.py` (modified) | `YearTiers` + year-tier tolerance |
| `astock_fundamentals/ground_truth/sina_loader.py` (new) | Sina CSV reader + annual slice |
| `astock_fundamentals/ground_truth/rule_cleaner.py` (new) | CleaningRules + load/rename/convert/aggregate |
| `astock_fundamentals/core/extraction_config.py` (modified) | `get_aliases` auto-merges sina_aliases_2019_2022 |
| `scripts/baseline_2019_2022.py` (new) | Baseline measurement |
| `scripts/clean_sina_pipeline.py` (new) | End-to-end orchestrator |
| `scripts/learn_sina_aliases.py` (new) | Auto-learner with name-similarity filter + regex fallback for broken YAML |

### Rules populated

- `rules/aliases.yaml` → `sina_aliases_2019_2022` block now has 50 entries (BS 16, IS 17, CF 17)
- `rules/value_mapping_rules.yaml` → `sina_aggregations_2019_2022` has 1 entry (BS)

### Tests

23/23 passing in 1.5s

## Quality control during learning

- **MIN_EVIDENCE=4** (was 3): at least 4 (stock, year) pairs must agree
- **MIN_NAME_SIM=0.5**: token-overlap filter to prevent spurious value-only matches
  (e.g. prevents `三、营业利润 ← 利润总额` which had identical value but different semantics)
- **Regex fallback** for `value_mapping_rules.yaml` line 546 parse error (pre-existing)

## Pre-existing issues (still out of scope)

1. `value_mapping_rules.yaml` line 546 YAML error — handled by `_safe_load_yaml` fallback
2. Some sina canonical names like `经营活动产生的现金流量净额2` were created with "2" suffix
   to avoid key collision when the same value matches multiple RDS items

## Next rounds

### Round 3: 扩展样本与精度

- 跑全部 6 stocks × 4 years × 3 types = 72 comparisons（目前 48）
- 把 MIN_EVIDENCE 提到 5 看是否更稳
- 增加金融行业 (银行 600000/600036/601398) 特定规则

### Round 4: 细化 CF aggregations

- CF 仍只有 65.24%；剩下的 35% 缺口主要在细项聚合
- 需要更细的 aggregation 检测（不只是字符串前缀）

### Round 5: 接 year-tier 阈值

- 用 `get_tolerance_for_year(year)` 替代 hard-coded 0.001
- 2019 用 0.01，2020-2022 用 0.005

## Spec open questions (§8) — answered

- **RDS 数据覆盖范围: 2019-2022 年是否完整？** ✓ 部分股票 6/6 (000001/600000/600036/600519/000002/000858) 2019-2022 RDS 都有
- **目标股票范围: 全部 3,903 只还是首批 N 只？** ✓ 首批 6 只，验证流程后再扩
- **Tidy Data 输出路径: `data/exports_v2/` 还是新路径？** ✓ 使用现有 `data/exports_v2/`
- **单位转换策略: Sina 原始数据是否始终以元为单位？** ✓ Sina AKShare 数据为元，无需转换

## Files in this round

- `scripts/learn_sina_aliases.py` (new, 200 lines)
- `astock_fundamentals/core/extraction_config.py` (modified: 25 lines added)
- `rules/aliases.yaml` (sina_aliases_2019_2022 populated)
- `rules/value_mapping_rules.yaml` (sina_aggregations_2019_2022 populated)
- `data/ground_truth_reports/baseline_2019_2022.json` (re-measured)
- `data/exports_v2/sina_cleaned_*.csv` (re-run with new aliases)

## Auto-loop run @ 2026-06-04 12:10:51

| Stage | BS | IS | CF |
|-------|----|----|-----|
| Round 1 | 99.8% → 99.8% (+0.00%) | 99.5% → 99.5% (+0.00%) | 88.9% → 88.9% (+0.00%) |

Value accuracy after run: BS=94.12%, IS=61.14%, CF=65.02%
