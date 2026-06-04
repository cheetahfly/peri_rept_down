# Sina→RDS Cleaning Progression (2019-2022)

> 第一轮: 2019-2022 baseline + scaffolding

## Run summary (2026-06-04)

- 4 stocks processed: 000001, 600000, 600036, 600519
- Years: 2019, 2020, 2021, 2022
- Pipeline: `scripts/clean_sina_pipeline.py` ran end-to-end (exit 0)
- Output: 3 CSVs in `data/exports_v2/sina_cleaned_{balance_sheet,income_statement,cash_flow}.csv`

## Row counts (Task 10 run)

| Statement | Input rows (cleaned df) | Tidy rows written | Stocks |
|-----------|------------------------|-------------------|--------|
| balance_sheet | 16 | 0 | 4 |
| income_statement | 16 | 0 | 4 |
| cash_flow | 16 | 0 | 4 |

**为什么 Tidy 是 0 行**: `field_order.yaml` 键是 RDS 字段编码（`F006N`、`F077N` 等），而 Sina CSV 列名是中文（如 `现金及存放中央银行款项`）。`rename_columns` 只能把 Sina 列名转成 `aliases.yaml` 里的 RDS **中文**名（如 `货币资金`），但 `_tidy_rows` 用 `field_name in df.columns` 检查时，找的是 F006N 而非 `货币资金`。需要在 Tidy 生成时按 RDS 中文名→F006N 编码的二次映射，或在 `_tidy_rows` 中用 `decode_mappings_by_type.json` 反向查表。

## Baseline match rates (2019-2022, from baseline_2019_2022.json)

| Statement | Match rate | Avg value accuracy |
|-----------|-----------|-------------------|
| balance_sheet | **99.37%** (632/636) | 81.11% |
| income_statement | **85.42%** (410/480) | 57.62% |
| cash_flow | **58.88%** (335/569) | 67.00% |

48 total comparisons (15 BS + 18 IS + 15 CF; some (stock, year) pairs missing in RDS).

对比 `sina_vs_rds_comparison.md` 2000-2021 全量数据 (BS 83.7%, IS 86.3%, CF 63.6%)：2019-2022 BS 显著提升 (99.37% vs 83.7%)，IS 略降，CF 略降。可能与样本差异 (6 stocks vs 100 stocks) 和时间窗口 (2019-2022 vs 2000-2021) 有关。

## What's been built (Tasks 1-9)

| Task | Module | Status |
|------|--------|--------|
| 1 | year-tier tolerance (`comparator.YearTiers`) | ✓ 6 tests |
| 2 | `sina_loader.SinaLoader` + slice helpers | ✓ 5 tests |
| 3 | `rule_cleaner` core (load + rename + convert) | ✓ 5 tests |
| 4 | Baseline measurement script + JSON | ✓ ran successfully |
| 5 | `rule_cleaner.apply_aggregations` | ✓ 2 tests |
| 6 | `clean_sina_pipeline.py` orchestrator | ✓ 1 e2e test |
| 7 | `aliases.yaml` sina_aliases_2019_2022 scaffold | ✓ YAML parses |
| 8 | `value_mapping_rules.yaml` sina_aggregations scaffold | ✓ 8 tests |
| 9 | Wire sina rules into `load_cleaning_rules` | ✓ 9 tests |

Total: **9 modules, 30+ tests, 1 baseline measurement** committed.

## Next rounds (未实现)

### Round 1: 完成 Tidy 端到端（最小补丁）
- 在 `_tidy_rows` 中用 `decode_mappings_by_type.json` 把 RDS 中文名→F006N 编码，建立反向索引
- 或在 `rename_columns` 后增加一步 `chinese_to_code` 用 `field_order.yaml` 反向
- 预期: Tidy 立即有数据（每只股票×每年约 50-100 行）

### Round 2: 填充 `sina_aliases_2019_2022`
- 跑 `auto_learner` 跑 2019-2022 全量对比
- 把高 confidence 候选对写入 `sina_aliases_2019_2022`
- 预期: CF 匹配率从 58.88% 提升

### Round 3: 填充 `sina_aggregations_2019_2022`
- 从 baseline 报告的 `unmatched` 项中发现 Sina 细项
- 写入 sum/first 规则
- 预期: CF 大幅提升 (细项→汇总)

### Round 4: 年份段策略接入
- 用 Task 1 的 `get_tolerance_for_year` 喂入 `compare_stock` 的 `value_error_pct` 阈值
- 预期: 各年份段稳定性提升

### Round 5: 重新测量 + 报告
- 跑 `scripts/baseline_2019_2022.py` 记录 round 4 后的 BS/IS/CF 匹配率
- 写入本文件的"Round delta"表

## Pre-existing issues encountered (out of plan scope)

- `value_mapping_rules.yaml` line 546 存在 YAML 解析错误（`value_match_thresholds` 段结构异常）。`load_cleaning_rules` 用 try/except 优雅降级，不影响本轮工作。
- `aliases.yaml` 是嵌套结构 (`balance_sheet.annual.<canonical>`) 而 `rename_columns` 期望扁平 (`balance_sheet.<canonical>`)，导致生产环境的 rename 不生效。本轮 `sina_aliases_2019_2022` 已正确放入 `annual` 层，但 `_build_reverse_alias_map` 仍查扁平层 — 在 Round 2 填充别名时会暴露，需在 Round 1 之前修复。
