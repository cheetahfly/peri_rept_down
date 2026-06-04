# peri_rept_down → astock_fundamentals

A股上市公司财务数据多源清洗流水线

## 核心能力

从多个数据源获取A股财报，通过规则引擎清洗为统一的 **RDS 标准化 Tidy Data**：

| 数据源 | 接入方式 | 覆盖 |
|--------|---------|------|
| RDS (cninfo) | `astock_fundamentals/sources/rds/` | 4,836 stocks, 1991-2022 |
| Sina (AKShare) | `astock_fundamentals/sources/api/` | 3,903 stocks, 1989-2026+ |
| PDF (年报原文) | `astock_fundamentals/sources/pdf/` | 按需 |

## 清洗流水线

```
Sina 原始数据 (data/akshare_bulk/)  ──→  SinaLoader (年度切片)
                                    ──→  comparator.compare_stock (别名+值匹配)
                                    ──→  rule_cleaner (重命名/聚合/单位)
                                    ──→  Tidy Data CSV (display_order)
```

**当前匹配率** (20 stocks × 2019-2022):

| 报表 | 匹配率 | 
|------|--------|
| 资产负债表 (BS) | **99.77%** |
| 利润表 (IS) | **99.52%** |
| 现金流量表 (CF) | **88.93%** (直接法子集) |

## 快速开始

### 1. 测量基线

```bash
# 跑 baseline 对比
python scripts/baseline_2019_2022.py
# 产出: data/ground_truth_reports/baseline_2019_2022.json

# 按行业筛选
python scripts/baseline_2019_2022.py  # 读取 expanded_stock_list.txt
```

### 2. 清洗流水线

```bash
# 单股票
python scripts/clean_sina_pipeline.py --stocks 000001 600000 --years 2019 2020 2021 2022

# 按行业
python scripts/clean_sina_pipeline.py --industries banking --years 2019 2020 2021 2022
python scripts/clean_sina_pipeline.py --industries banking insurance --years 2019 2020 2021 2022

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
pytest tests/ -q           # 30 tests in ~3s
pytest tests/ground_truth/ # 单元测试
pytest tests/scripts/      # E2E + 行业
```

## 项目结构

```
astock_fundamentals/       # 核心包
├── core/                  # 配置、日志、模型、管线
├── ground_truth/          # 对比引擎、规则学习、清洗器
│   ├── comparator.py      # RDS vs Sina 匹配引擎
│   ├── auto_learner.py    # 自动学习别名
│   ├── rule_cleaner.py    # 规则应用 (rename/convert/aggregate)
│   ├── sina_loader.py     # Sina CSV 读取 + 年度切片
│   └── cf_indirect_calculator.py  # CF 间接法推算
├── sources/               # 数据源适配
│   ├── api/               # AKShare / Tushare / Wind
│   ├── rds/               # cninfo RDS 加载器
│   └── pdf/               # PDF 解析器
└── storage/               # SQLite 存储

rules/                     # 外置规则 (YAML)
├── aliases.yaml           # 别名映射 (300+ entries)
├── value_mapping_rules.yaml   # 值映射规则 (1,024 lines)
├── field_order.yaml       # RDS 字段 display_order (245 codes)
├── cf_direct_items.yaml   # CF 直接法白名单 (49 items)
├── industry_aliases.yaml  # 行业→股票代码映射 (8 industries)
├── indirect_cf_formulas.yaml  # CF 间接法推算公式
├── skip_items.yaml        # 跳过的非财务项
├── validation_rules.yaml  # 表内勾稽规则
└── regulatory_documents/  # 7 份 CAS 法规参考

scripts/                   # 脚本
├── baseline_2019_2022.py     # 基线测量
├── clean_sina_pipeline.py    # 流水线编排 (--industries)
├── learn_sina_aliases.py     # 规则学习
├── learn_clean_loop.py       # 闭环 auto-loop
└── ... (下载/对比/报告工具)

data/
├── akshare_bulk/          # Sina 原始 CSV (1.9 GB, .gitignored)
├── decode_mappings_by_type.json  # F006N → 中文名
├── exports_v2/            # Tidy Data 输出
└── ground_truth_reports/  # 基线/审计/进度报告

docs/
├── demo_results.html      # 交互式成果仪表盘
└── superpowers/           # 设计文档和计划
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

## License

MIT
