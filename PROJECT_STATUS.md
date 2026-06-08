# 项目状态报告

更新时间: 2026-06-08

## 项目概述

A股财务数据多源清洗流水线 — Sina (AKShare) ↔ RDS (cninfo) ↔ Guosen (国信) ↔ PDF 年报

详细审计报告: [`docs/audit/2026-06-08-rules-data-quality.md`](docs/audit/2026-06-08-rules-data-quality.md)

## 当前进度

### 核心指标 (2026-06-08, 47,966 对比)

| 报表 | 名义匹配率 | 值准确率 | RDS 字段总数 | 对比数 |
|------|------------|----------|--------------|--------|
| 资产负债表 (BS) | **99.73%** | 94.87% | 638,314 | 15,965 |
| 利润表 (IS) | **99.79%** | 88.89% | 393,930 | 16,136 |
| 现金流量表 (CF) | **96.87%** | 95.72% | 462,032 | 15,865 |
| **合计** | — | — | 1,494,276 | **47,966** |

数据来源: `data/ground_truth_reports/baseline_2019_2022.json` (3,903 stocks × 7 年抽样 × 3 报表)

### 分行业匹配率 (1,191 stocks, 6 前缀)

| 前缀 | 股票数 | 匹配率 | 备注 |
|------|--------|--------|------|
| 000 (深市主板) | 200 | 98.76% | 略低 |
| 002 (深市中小板) | 200 | 99.62% | |
| 300 (创业板) | 200 | 99.85% | |
| 600 (沪市主板) | 199 | 98.99% | 银行占比高 |
| 601 (沪市大盘) | 192 | 99.10% | |
| 603 (沪市中小) | 200 | 99.86% | |
| **合计** | **1,191** | **99.26%** | |

### 已完成功能 (2026-06-08)

- [x] Sina→RDS 清洗流水线 (Step 1-5)
- [x] 别名自动学习 (300+ aliases, 50 high-confidence)
- [x] CF 直接法/间接法分离
- [x] IS normalize-key clone 修复 (where/减/加 前缀剥离后 alias 查找)
- [x] 行业参数化 (8 industries → stock code mapping)
- [x] 自动闭环 (baseline → learn → re-measure)
- [x] 1,191 stocks baseline (6 prefix groups)
- [x] **3,903 stocks × 7 年全量 baseline (47,966 对比)** — 2026-06-04
- [x] 交互式成果仪表盘 (ECharts HTML)
- [x] Guosen 第三方数据源接入
- [x] display_order sequential bug 修复 (2026-06-08)
- [x] **P0-1a `rule_cleaner` rename_columns bug 修复 (2026-06-08)** — CF 银行专项恢复

### 匹配率迭代历史

| Round | BS | IS | CF | 关键修复 | 来源 |
|-------|----|----|----|---------|------|
| Round 0 | 99.37% | 87.85% | 65.24% | 基线 | |
| Round 1 | 99.38% | 89.06% | 72.73% | 50 aliases | |
| Round 2 | 99.38% | 89.06% | 90.98% | CF 直接法过滤 | |
| Round 3 | 99.38% | 98.23% | 90.98% | IS normalize-key clone | |
| Round 4 | 99.38% | 98.23% | 90.98% | YAML 修复 | |
| Round 5 (20 stk) | 99.77% | 99.52% | 88.93% | 样本扩展 (CF 因工业股↓) | |
| **Round 6 (1,191 stk × 7 年)** | **99.73%** | **99.79%** | **96.87%** | 早期别名 (2000-2010) | 2026-06-04 |
| **Round 7 (3,903 stk × 7 年)** | **99.73%** | **99.79%** | **96.87%** | 早期别名 + 行业规则 | 2026-06-07 |

### 架构

```
Sina (AKShare)                    RDS (cninfo)
     │                                 │
     ├── SinaLoader ──┐    ┌── RdsLoader ──┤
     │                 │    │               │
     └── comparator.compare_stock ──────────┘
                       │
                       ├── 别名匹配 (aliases.yaml, 300+ entries)
                       ├── 值全等匹配 (0.001 tol)
                       ├── normalize-key clone (fix 其中：/减：/加：)
                       └── CF 直接法白名单 (cf_direct_items.yaml)
                       │
                       ▼
                  rule_cleaner
                       │
                       ├── rename_columns (别名) ⚠ P0-1a bug 待修
                       ├── convert_values (单位)
                       └── apply_aggregations (细项→汇总)
                       │
                       ▼
                  Tidy Data CSV
            (stock_code | year | field_code | value | display_order)
```

### 待处理 (按优先级)

| 优先级 | 项目 | 预估影响 | 状态 |
|--------|------|----------|------|
| **P0-1a** | `rule_cleaner._build_reverse_alias_map` bug | 清洗输出缩水 | ✅ **已修复 2026-06-08 (56d03e7c)** |
| P0-2a | 13 PDF 测试因 `data/by_code/600016/` 缺失失败 | 整套 PDF 测试不可信 | 待重下数据 |
| P0-2c | `test_expansion.py::test_stock` fixture 错误 | 扩展测试不可用 | 15 min 修复 |
| P0-4 | `baseline_per_year.json` 2022 数据全 0 | 报告不可信 | 待决策 |
| P1-1 | IS 值准确率 88.89% (银行 IS 2021 已知) | 银行专项未解决 | 持续优化 |
| P1-2 | F057N 等银行专项别名文档化 | 规则透明 | 30 min |
| P1-3 | `aliases_flat.yaml.bak` 373 行备份 | 仓库冗余 | 5 min |
| P2-1 | CF 间接法推算规则覆盖验证 | 100% CF 难达 | 3-4 h |
| P3-1 | Tushare/Wind 第二数据源 | 数据多元化 | 未知 |
| P3-2 | GitHub Actions CI/CD | 持续集成 | 未知 |

### 测试覆盖

- **总测试数**: 315 (替代过时的"30 tests")
- **通过**: 289
- **失败**: 14
- **错误**: 1
- **跳过**: 13
- **总耗时**: 11 分 49 秒
- **覆盖模块**: comparator/year-tier, sina_loader, rule_cleaner, pipeline e2e, industry CLI, rds_loader_tidy

### 已知限制

- CF 间接法调节项: Sina 不提供, 当前过滤出度量范围
- RDS 2021 bank 数据异常 (与 Sina 同科目值差 >35%)
- `baseline_per_year.json` 2022 数据全为 0 (scope 声明包含 2022 但实际未跑)
- `data/akshare_bulk/` (1.9 GB) 已在 .gitignore, 保留于磁盘
- **P0-1a bug** ✅ 已修复: `rule_cleaner._build_reverse_alias_map` 误把 period 当 canonical (修复于 56d03e7c)，修复后 IS 17 字段、CF 34 字段、BS 32 字段 (清洗输出从 49/24/66 行扩到 231/128/244 行)

### 开发历史 (本会话累计)

- 78+ commits pushed to origin/master
- 3 个核心修复 (normalize-key clone, RULES_DIR path, CF direct filter)
- 4 个 feature (行业 CLI, 闭环, 间接法推算器, Guosen 接入)
- 1 个成果展示页 (ECharts HTML)
- 1 份规则与数据质量审计报告 (2026-06-08)
- 1 个 display_order bug 修复 (2026-06-08)
- 1 个 P0-1a 严重 bug 发现 (2026-06-08)
