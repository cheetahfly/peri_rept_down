# peri_rept_down → astock_fundamentals

A股上市公司财务数据多源清洗流水线

> **最近更新**: 2026-06-08
> **当前基线**: 3,903 stocks × [2000, 2005, 2010, 2015, 2018, 2020, 2022] × 3 statements = **47,966 对比**
> **详细审查**: 见 [`docs/audit/2026-06-08-rules-data-quality.md`](docs/audit/2026-06-08-rules-data-quality.md)

## 核心能力

从多个数据源获取 A 股财报，通过规则引擎清洗为统一的 **RDS 标准化 Tidy Data**：

| 数据源 | 接入方式 | 覆盖 |
|--------|---------|------|
| RDS (cninfo) | `astock_fundamentals/sources/rds/` | 4,836 stocks, 1991-2022 |
| Sina (AKShare) | `astock_fundamentals/sources/api/` | 3,903 stocks, 1989-2026+ |
| Guosen (国信) | `astock_fundamentals/sources/guosen/` | 按需, 需 API key |
| PDF (年报原文) | `astock_fundamentals/sources/pdf/` | 按需 |

## 当前匹配率 (2026-06-08 基线, 47,966 对比)

| 报表 | 名义匹配率 | 值准确率 | 对比数 |
|------|------------|----------|--------|
| 资产负债表 (BS) | **99.73%** | 94.87% | 15,965 |
| 利润表 (IS) | **99.79%** | 88.89% | 16,136 |
| 现金流量表 (CF) | **96.87%** | 95.72% | 15,865 |

数据来源: `data/ground_truth_reports/baseline_2019_2022.json`

### 分行业匹配率 (1,191 stocks, 6 前缀)

| 前缀 | 股票数 | 匹配率 |
|------|--------|--------|
| 000 (深市主板) | 200 | 98.76% |
| 002 (深市中小板) | 200 | 99.62% |
| 300 (创业板) | 200 | 99.85% |
| 600 (沪市主板) | 199 | 98.99% |
| 601 (沪市大盘) | 192 | 99.10% |
| 603 (沪市中小) | 200 | 99.86% |
| **合计** | **1,191** | **99.26%** |

### 分年度匹配率 (7 年抽样, ⚠ 2022 数据缺失)

| 年份 | BS | IS | CF |
|------|-----|------|------|
| 2000 | 96.11% | 99.93% | 96.48% |
| 2005 | 97.77% | 100.00% | 99.75% |
| 2010 | 99.65% | 100.00% | 99.72% |
| 2015 | 98.89% | 99.98% | 98.90% |
| 2018 | 99.56% | 99.53% | 99.37% |
| 2020 | 99.53% | 99.83% | 99.22% |
| **2022** | **0.00%** ⚠ | **0.00%** ⚠ | **0.00%** ⚠ |

## 清洗流水线

```
Sina 原始数据 (data/akshare_bulk/)  ──→  SinaLoader (年度切片)
                                    ──→  comparator.compare_stock (别名+值匹配)
                                    ──→  rule_cleaner (重命名/聚合/单位)
                                    ──→  Tidy Data CSV (display_order)
```

## 快速开始

### 1. 测量基线

```bash
# 跑 baseline 对比 (全量 3,903 stocks, 47,966 对比)
python scripts/baseline_2019_2022.py
# 产出: data/ground_truth_reports/baseline_2019_2022.json

# 按行业筛选
python scripts/baseline_2019_2022.py --industries banking
```

### 2. 清洗流水线

```bash
# 单股票
python scripts/clean_sina_pipeline.py --stocks 000001 600000 --years 2019 2020 2021 2022

# 按行业
python scripts/clean_sina_pipeline.py --industries banking --years 2019 2020 2021 2022

# 特殊: 'all' 用 default_pool, 'none' 跳过行业只用手动 --stocks
```

### 3. 自动学习 + 清洗闭环

```bash
python scripts/learn_clean_loop.py --industries all --rounds 3 --min-delta 0.005

# 或手动执行两步
python scripts/learn_sina_aliases.py --industries banking
python scripts/baseline_2019_2022.py
```

### 4. 运行测试

```bash
pytest tests/ -q                # ~315 tests, ~12 min
pytest tests/ground_truth/      # 单元测试
pytest tests/scripts/           # E2E + 行业
```

## 项目结构

```
astock_fundamentals/       # 核心包
├── core/                  # 配置、日志、模型、流水线
├── ground_truth/          # 对比引擎、规则学习、清洗器
│   ├── comparator.py      # RDS vs Sina 匹配引擎
│   ├── auto_learner.py    # 自动学习别名
│   ├── rule_cleaner.py    # 规则应用 (rename/convert/aggregate) ⚠ P0-1a bug
│   ├── sina_loader.py     # Sina CSV 读取 + 年度切片
│   └── cf_indirect_calculator.py  # CF 间接法推算
├── sources/               # 数据源适配
│   ├── api/               # AKShare / Tushare / Wind (TODO)
│   ├── rds/               # cninfo RDS 加载器
│   ├── guosen/            # Guosen API
│   └── pdf/               # PDF 解析器
└── storage/               # SQLite 存储

extraction/                # 旧版 PDF 提取与 RDS 加载
└── ground_truth/rds_loader.py  # (display_order bug 已修复 2026-06-08)

rules/                     # 外置规则 (YAML)
├── aliases.yaml           # 别名映射 (~3 statements × 4 periods)
├── value_mapping_rules.yaml   # 值映射规则 (156 value_match_pairs, 43 auto_learned)
├── field_order.yaml       # RDS 字段 display_order (IS 55 + BS 107 + CF 83)
├── cf_direct_items.yaml   # CF 直接法白名单 (49 items)
├── industry_aliases.yaml  # 行业→股票代码映射 (8 industries)
├── indirect_cf_formulas.yaml  # CF 间接法推算公式
├── skip_items.yaml        # 跳过的非财务项 (22 items)
├── validation_rules.yaml  # 表内勾稽规则
├── unit_detection.yaml    # 单位识别
├── section_keywords.yaml  # 报表页面关键词
└── regulatory_documents/  # CAS 法规参考

scripts/                   # 脚本
├── baseline_2019_2022.py     # 基线测量
├── clean_sina_pipeline.py    # 流水线编排
├── learn_sina_aliases.py     # 规则学习
├── learn_clean_loop.py       # 闭环 auto-loop
└── ... (下载/对比/报告工具)

data/
├── akshare_bulk/          # Sina 原始 CSV (1.9 GB, .gitignored)
├── decode_mappings_by_type.json  # F006N → 中文名
├── exports_v2/            # Tidy Data 输出 (3 个 sina_cleaned_*.csv)
└── ground_truth_reports/  # 基线/审计/进度报告

docs/
├── audit/                 # 审计报告
│   └── 2026-06-08-rules-data-quality.md
├── superpowers/           # 设计文档和计划
└── SINA_RULE_OPTIMIZATION_PLAN.md
```

## 技术栈

- Python 3.13, pandas, pyreadr, PyYAML, argparse, pytest
- 规则引擎: YAML 外置化, normalize_name 前缀剥离 + normalize-key clone
- 清洗器: column rename → value conversion → aggregation → tidy output
- 匹配链: exact → exact_norm → alias → reverse_alias → fuzzy → cid_value → value_exact

## 关键决策

- **规则外置**: 所有映射存入 YAML (`rules/`)，代码只做匹配
- **直间分离**: CF 分直接法和间接法子集，Sina 只有直接法数据
- **前缀剥离**: `normalize_name` 去掉 `其中：`/`减：`/`加：` 前缀后，通过 normalize-key clone 保证 alias 可查
- **行业参数化**: 通过 `rules/industry_aliases.yaml` 将行业名转为股票代码

## 当前已知问题

| 优先级 | 问题 | 状态 |
|--------|------|------|
| **P0-1a** | `rule_cleaner._build_reverse_alias_map` 将 period 当 canonical，导致清洗输出缩水 | 待修复 (详见审计报告) |
| P0-2a | `test_word_recovery` 13 个 PDF 测试因 `data/by_code/600016/` 缺失 | 数据缺失 |
| P0-4 | `baseline_per_year.json` 2022 年数据全 0 | 待决策 (重跑或修正 scope) |
| P1-1 | IS 值准确率 88.89% (银行 IS 2021 已知差异) | 持续优化 |
| P3-1 | Tushare/Wind 第二数据源 | 待启动 |
| P3-2 | GitHub Actions CI/CD | 待启动 |

## License

MIT
