# 项目状态报告

更新时间: 2026-06-04

## 项目概述

A股财务数据多源清洗流水线 — Sina (AKShare) ↔ RDS (cninfo) ↔ PDF 年报

## 当前进度

### 核心指标 (2026-06-04, 20 stocks × 180 comparisons)

| 报表 | 匹配率 | 值准确率 | 比较数 |
|------|--------|---------|--------|
| 资产负债表 (BS) | **99.77%** | 94.12% | 60 |
| 利润表 (IS) | **99.52%** | 61.14% | 60 |
| 现金流量表 (CF) | **88.93%** | 65.02% | 60 |

### 已完成功能

- [x] Sina→RDS 清洗流水线 (Step 1-5)
- [x] 别名自动学习 (188 rules → 50 high-confidence)
- [x] CF 直接法/间接法分离
- [x] IS normalize-key clone 修复 (where/减/加 前缀剥离后 alias 查找)
- [x] 行业参数化 (8 industries → stock code mapping)
- [x] 自动闭环 (baseline → learn → re-measure)
- [x] 120-stock baseline (7 prefix groups)
- [x] 交互式成果仪表盘 (ECharts HTML)
- [x] 项目文档更新
- [x] Git 清理 + 推送

### 匹配率迭代历史

| Round | BS | IS | CF | 关键修复 |
|-------|----|----|----|---------|
| Round 0 | 99.37% | 87.85% | 65.24% | 基线 |
| Round 1 | 99.38% | 89.06% | 72.73% | 50 aliases |
| Round 2 | 99.38% | 89.06% | 90.98% | CF 直接法过滤 |
| Round 3 | 99.38% | 98.23% | 90.98% | IS normalize-key clone |
| Round 4 (6 stk) | 99.38% | 98.23% | 90.98% | YAML 修复 |
| **Round 5 (20 stk)** | **99.77%** | **99.52%** | **88.93%** | 样本扩展 (CF 因工业股↓) |

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
                       ├── rename_columns (别名)
                       ├── convert_values (单位)
                       └── apply_aggregations (细项→汇总)
                       │
                       ▼
                  Tidy Data CSV
            (stock_code | year | field_code | value | display_order)
```

### 待处理

| 优先级 | 项目 | 预估影响 |
|--------|------|---------|
| P1 | CF 间接法数值推算 |
| P2 | RDS 值准确率改善 (bank IS 2021) |
| P3 | Tushare/Wind 第二数据源 |
| P4 | GitHub Actions CI/CD |

### 测试覆盖

- **30 tests** passing in ~3s
- Coverage: comparator/year-tier, sina_loader, rule_cleaner, pipeline e2e, industry CLI

### 已知限制

- CF 间接法调节项 : Sina 不提供, 当前过滤出度量范围
- RDS 2021 bank 数据异常 (与 Sina 同科目值差 >35%)
- value_mapping_rules.yaml line 546 已修复
- data/akshare_bulk/ (1.9 GB) 已在 .gitignore, 保留于磁盘

### 开发历史 (本会话)

- 13 个计划任务完成
- 3 个核心修复 (normalize-key clone, RULES_DIR path, CF direct filter)
- 3 个 feature (行业 CLI, 闭环, 间接法推算器)
- 1 个成果展示页 (ECharts HTML)
- 47 commits pushed to origin/master
