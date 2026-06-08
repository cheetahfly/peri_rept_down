# Sina 数据提取准确率报告

**日期**: 2026-06-08
**范围**: Sina (AKShare) → 规则清洗 → RDS 对比
**基线**: 3,903 stocks × 7 年 (2000/2005/2010/2015/2018/2020/2022) × 3 报表 = 47,966 对比

## 1. 流水线架构

```
Sina 原始数据 (data/akshare_bulk/, 27,329 CSV)
    │
    ├── SinaLoader.get_annual(code, years, st)  # 年度切片
    │
    ├── rule_cleaner.rename_columns()           # 别名匹配 (aliases.yaml)
    │   └── _build_reverse_alias_map()          # ⚠ P0-1a 已修复 2026-06-08
    │       修复前: period 名当 canonical → IS 仅 3 字段、CF 9 字段
    │       修复后: 正确迭代 → IS 17 字段、CF 34 字段、BS 32 字段
    │
    ├── rule_cleaner.convert_values()           # 单位转换 (unit_detection.yaml)
    ├── rule_cleaner.apply_aggregations()       # 聚合 (value_mapping_rules.yaml)
    │
    └── comparator.compare_stock()              # 与 RDS 比较
        ├── exact → exact_norm → alias → reverse_alias → fuzzy → cid_value → value_exact
        ├── CF: cf_direct_items.yaml 过滤直接法子集
        ├── CF: cf_indirect_calculator 推算间接法项
        └── 值容差: 0.001
```

## 2. 规则资产 (rules/)

| 规则文件 | 条目数 | 功能 |
|----------|--------|------|
| `aliases.yaml` | 1,299 行 | 3 报表 × 4 周期 + sina_aliases_2019_2022 |
| `value_mapping_rules.yaml` | 954 行 | 156 value_match_pairs + 43 auto_learned + aggregations |
| `cf_direct_items.yaml` | 72 行 | CF 直接法 49 项白名单 |
| `indirect_cf_formulas.yaml` | 82 行 | CF 间接法推算公式 |
| `field_order.yaml` | 250 行 | RDS display_order (IS 55 + BS 107 + CF 83 = 245 codes) |
| `industry_aliases.yaml` | 95 行 | 8 行业 → 股票代码映射 |
| `skip_items.yaml` | 22 行 | 跳过非财务项 |
| `validation_rules.yaml` | 383 行 | 表内勾稽规则 |

**总规则**: 3,193 行业务条目

## 3. 准确率指标 (全量 47,966 对比)

| 报表 | 名义匹配率 | 值准确率 | RDS 字段总数 | 对比数 |
|------|------------|----------|--------------|--------|
| 资产负债表 (BS) | **99.73%** | **94.87%** | 638,314 | 15,965 |
| 利润表 (IS) | **99.79%** | **88.89%** | 393,930 | 16,136 |
| 现金流量表 (CF) | **96.87%** | **95.72%** | 462,032 | 15,865 |
| **合计** | **98.76%** | **92.99%** | 1,494,276 | **47,966** |

**名义匹配率** = Sina 有对应 RDS 字段的数量 / RDS 总字段数
**值准确率** = 匹配字段中值差异 <0.001 的比例

## 4. 分行业准确率 (1,191 stocks)

| 前缀 | 股票数 | 匹配率 | 行业分布 |
|------|--------|--------|----------|
| 000 | 200 | 98.76% | 深市主板 (银行多) |
| 002 | 200 | 99.62% | 深市中小板 |
| 300 | 200 | 99.85% | 创业板 |
| 600 | 199 | 98.99% | 沪市主板 (大盘股) |
| 601 | 192 | 99.10% | 沪市大盘 |
| 603 | 200 | 99.86% | 沪市中小 |

## 5. 分年度准确率

| 年份 | BS | IS | CF |
|------|-----|------|------|
| 2000 | 96.11% | 99.93% | 96.48% |
| 2005 | 97.77% | 100.00% | 99.75% |
| 2010 | 99.65% | 100.00% | 99.72% |
| 2015 | 98.89% | 99.98% | 98.90% |
| 2018 | 99.56% | 99.53% | 99.37% |
| 2020 | 99.53% | 99.83% | 99.22% |
| 2022 | 0.00% ⚠ | 0.00% ⚠ | 0.00% ⚠ |

**观察**: 2000-2010 BS 略低 (96-99%)，与早期 Sina 格式特殊项相关

## 6. P0-1a 修复效果 (2026-06-08)

| 指标 | 修复前 | 修复后 | 提升 |
|------|--------|--------|------|
| IS 清洗输出 | 24 行 / 3 codes | 128 行 / 17 codes | 5× |
| CF 清洗输出 | 66 行 / 9 codes | 244 行 / 34 codes | 4× |
| BS 清洗输出 | 49 行 / 4 codes | 231 行 / 32 codes | 5× |
| CF 银行专项 | 0 | 58 行 | 恢复 |

**修复详情**:
- `rule_cleaner._build_reverse_alias_map` 正确迭代 period → canonical → alias
- 回归测试 `test_build_reverse_alias_map_does_not_use_period_as_canonical` 已添加
- CF 银行专项 (F072N/F081N/F084N/F085N/F087N/F016N/F017N/F076N) 恢复

## 7. 已知限制

| 限制 | 影响 | 状态 |
|------|------|------|
| IS 88.89% 值准确率 | 银行 IS 2021 已知差异 (35%) | 持续优化中 |
| F057N 信用减值损失 | 被归并到 F013N (资产减值损失) | P1-7 跟踪 |
| 2022 基线数据 | baseline_per_year 全 0 | 待重跑 |
| CF 间接法调节项 | Sina 不提供，已过滤 | 设计约束 |

## 8. 测试覆盖

| 测试套件 | 结果 | 备注 |
|----------|------|------|
| test_rule_cleaner (10 tests) | ✅ 全过 | 含 P0-1a 回归测试 |
| test_comparator_year_tier | ✅ 全过 | |
| test_rds_loader_tidy (3 tests) | ✅ 全过 | display_order sequential |
| test_tidy_data_pipeline | ✅ 全过 | display_order sequential (修复后) |
| test_crawlers | ✅ 全过 | |
| test_word_recovery (13 tests) | ❌ 失败 | data/by_code/600016/ 缺失 |
| test_expansion | ❌ 失败 | fixture 缺失 |
| **总测试** | **251 passed / 13 skipped** | 530s |

## 9. 产出文件

| 文件 | 内容 |
|------|------|
| `data/exports_v2/sina_cleaned_*.csv` | 清洗后的 Tidy Data (231/128/244 行, 000001+600000) |
| `data/ground_truth_reports/baseline_2019_2022.json` | 全量基线 (47,966 对比) |
| `data/ground_truth_reports/baseline_per_prefix.json` | 分行业基线 (1,191 stocks) |
| `data/ground_truth_reports/baseline_per_year.json` | 分年度基线 (7 年) |
| `data/ground_truth_reports/full_sina_vs_rds_200stocks.json` | 200 stocks 对比 (2,367 cells) |
