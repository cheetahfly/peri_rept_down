# Sina → RDS 标准化清洗流水线 设计文档

**日期**: 2026-06-04
**状态**: ✅ 已完成 (2026-06-04 验收通过)
**关联文档**: [[2026-05-28-tidy-data-pipeline-design]]

---

## 1. 目标

将已下载的 Sina 来源 (AKShare) 2019-2022 年财务数据，通过与 RDS (cninfo) 标准数据对比匹配，总结外置规则，用规则清洗 Sina 数据，输出为按 RDS 三大表财务指标项目和 display_order 排列的 Tidy Data。

### 成功指标

| 指标 | 当前基线 | 目标 |
|------|---------|------|
| BS 匹配率 | 83.7% | ≥ 90% |
| IS 匹配率 | 86.3% | ≥ 90% |
| CF 匹配率 | 63.6% | ≥ 75% |
| 值准确率 | 77.7% | ≥ 85% |

基线数据取自 `data/ground_truth_reports/sina_vs_rds_comparison.md` (100只股票 × 2000-2021)。本次聚焦 2019-2022。

---

## 2. 数据现状

### Sina 数据 (data/akshare_bulk/)

- 3,903 只股票，每只 7 种文件: `_raw.csv`, `_balance_sheet.csv`, `_income_statement.csv`, `_cash_flow.csv`, `_balance_sheet.json`, `_income_statement.json`, `_cash_flow.json`
- 列名: Sina 原始科目名 (如 `发放贷款及垫款净额`)，不是 RDS 的 F006N 编码
- 年份范围: 1989-2026Q1，按 `报告日` 列筛选
- 每行是一个报告期 (年报 12-31, 半年报 06-30, 季报 03-31/09-30)
- 单位: 元

### RDS 数据 (D:/Research/Quant/SETL/cninfo/data_backup)

- `.rds` 格式，通过 `pyreadr` 加载
- 每只股票 6 种文件: `b_f/b_o.rds` (BS), `pl_f/pl_o.rds` (IS), `cf_f/cf_o.rds` (CF)
- 列名: F006N 等字段编码，通过 `data/decode_mappings_by_type.json` 解码为中文名
- `rules/field_order.yaml`: 定义每种报表类型的 display_order (BS 107项, IS 55项, CF 83项)

---

## 3. 流水线设计

### 总图

```
Sina 原始数据 (data/akshare_bulk/XXXXXX_raw.csv)
  │  列名 = Sina 科目名
  │
  ├── Step 1: 年度切片 → 提取 2019-2022 年报 (报告日 = XXXX1231)
  │      ↓
  ├── Step 2: 名称匹配 → RDS 标准科目
  │      ┌─ 精确匹配 (rules/aliases.yaml 别名映射)
  │      ├─ 值全等匹配 (跨源值比较, 阈值 0.001)
  │      ├─ 行业特定匹配 (rules/value_mapping_rules.yaml 行业段)
  │      └─ 年份段阈值调整 (comparator year-tier)
  │      ↓
  ├── Step 3: 输出匹配报告 + 未匹配清单 → data/ground_truth_reports/
  │      ↓
  ├── Step 4: 学习新规则 (auto_learner)
  │      写入 rules/value_mapping_rules.yaml, rules/aliases.yaml
  │      ↓
  ├── Step 5: 用完整规则集重新清洗
  │      列重命名 (Sina名 → RDS字段编码)
  │      值单位转换 (Sina原始单位 → 元)
  │      科目拆分聚合 (Sina细项 → RDS汇总项)
  │      ↓
  └── 输出: Tidy Data
         stock_code | year | period | statement_type | field_code | field_name | value | display_order
```

### Step 1: 年度切片

**输入**: `data/akshare_bulk/XXXXXX_balance_sheet.csv` (等)
**操作**:
- 筛选 `报告日` 列，保留 `20191231, 20201231, 20211231, 20221231` (年报)
- 筛选 `类型` 列 = `合并期末` (合并报表)
- 提取列名作为 Sina 科目清单
**输出**: 每只股票 × 4 年的年报行，X× 列科目

### Step 2: 名称匹配

**输入**: Sina 年报行 + 同股票同年 RDS 数据
**操作**: 复用 `astock_fundamentals/ground_truth/comparator.py` 匹配引擎，策略链:

1. **精确名称匹配**: Sina 科目名 → `rules/aliases.yaml` → RDS 标准名
2. **值全等匹配**: 跨源值比较 (相对误差 ≤ 0.001)，发现隐藏映射
3. **行业特定匹配**: 金融股 (000001, 600000 等) 使用 `rules/value_mapping_rules.yaml` 行业段
4. **年份段阈值**: 2019-2020 标准阈值 (0.01), 2021-2022 严格阈值 (0.005)
**输出**: 每个 stock×year×statement_type 的 matched/unmatched 清单

### Step 3: 匹配报告

**输入**: Step 2 匹配结果
**输出**: `data/ground_truth_reports/sina_rds_matching_2019_2022.json`
结构:
```json
{
  "stock_code": "000001",
  "year": 2019,
  "statement_type": "balance_sheet",
  "total_sina_items": 120,
  "matched_count": 95,
  "unmatched_sina": ["买入返售金融资产", "存放联行款项", ...],
  "match_rate": 0.792
}
```
全局汇总: 按报表类型、年份、行业维度的匹配率表

### Step 4: 规则学习

**输入**: Step 3 的 `unmatched_sina` 清单 + RDS 侧的未匹配科目
**操作**: `astock_fundamentals/ground_truth/auto_learner.py` 分析未匹配项:
- 名称相似度 > 0.8 的候选对 → 建议别名
- 值近似匹配的候选对 → 建议 value_mapping 规则
- 行业特定的未匹配项 → 建议行业段规则
- 人工确认后写入 YAML
**输出**: 
- `rules/aliases.yaml` 增量追加
- `rules/value_mapping_rules.yaml` 增量追加

### Step 5: 规则清洗

**输入**: Sina 原始年度行 × 完整规则集
**操作**: 新模块 `astock_fundamentals/ground_truth/rule_cleaner.py`:

1. **列重命名**: Sina列名 → `aliases.yaml` → RDS字段编码 (F006N)
2. **值转换**: Sina单位 × `unit_detection.yaml` → 统一为元
3. **科目聚合**: Sina细项 → `value_mapping_rules.yaml` 聚合规则 → RDS汇总项
4. **缺失标记**: 无法匹配的 Sina 列标记为 `_unmatched`
5. **排序**: 按 `field_order.yaml` 的 display_order 重排列
**输出**: Tidy Data CSV
```
stock_code | year | period | statement_type | field_code | field_name | value | display_order
000001     | 2019 | annual | balance_sheet  | F006N      | 货币资金   | 1.23e11 | 0
000001     | 2019 | annual | balance_sheet  | F077N      | 结算备付金 | 4.56e10 | 1
...
```

---

## 4. 规则文件设计

### 现有规则 (复用)

| 文件 | 用途 | 当前规模 |
|------|------|---------|
| `rules/aliases.yaml` | Sina名 → RDS名 别名映射 | 30 KB |
| `rules/value_mapping_rules.yaml` | 行业特化/年份段/聚合规则 | 45 KB |
| `rules/field_order.yaml` | RDS 标准字段顺序 | 4.4 KB, 245码 |
| `rules/validation_rules.yaml` | 表内勾稽校验 | 17 KB |
| `rules/skip_items.yaml` | 跳过项 ("其中:"等) | 535 B |
| `rules/unit_detection.yaml` | 单位检测规则 | 470 B |

### 新增/修改规则结构

`rules/value_mapping_rules.yaml` 增量追加:
```yaml
# Sina → RDS 规则 (年: 2019-2022)
sina_to_rds:
  balance_sheet:
    # 精确别名 (来自 aliases.yaml 的外键)
    exact_aliases: []
    
    # 值全等匹配发现的映射
    value_discovered:
      - sina_name: "买入返售金融资产"
        rds_code: "F012N"
        confidence: 0.99
        evidence_years: [2019, 2020, 2021, 2022]
        evidence_stocks: [000001, 600000, 600036]
      
    # 行业特定映射
    industry_specific:
      banking:
        - sina_name: "存放联行款项"
          rds_code: "F083N"
        - sina_name: "拆出资金"
          rds_code: "F011N"
      insurance: []
      securities: []
      
    # 科目拆分聚合 (Sina 多个细项 → RDS 一个汇总项)
    aggregation_rules:
      - rds_code: "F078N"
        description: "其他应收款"
        sina_parts:
          - "其他应收款-合计"
          - "其他应收款-关联方"
          - "其他应收款-外部"
        operation: sum  # sum | first | max
  
  income_statement: ...
  cash_flow: ...
```

---

## 5. 文件变更计划

### 新增文件

| 文件 | 用途 |
|------|------|
| `scripts/clean_sina_pipeline.py` | 流水线主脚本，编排 Step 1-5 |
| `astock_fundamentals/ground_truth/rule_cleaner.py` | 规则应用器：列重命名、值转换、聚合 |
| `data/ground_truth_reports/sina_rds_matching_2019_2022.json` | Step 3 匹配报告 |
| `data/ground_truth_reports/cleaning_progression.md` | 增量清洗进度报告 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `rules/aliases.yaml` | 增量追加 2019-2022 新发现的别名 |
| `rules/value_mapping_rules.yaml` | 新增 `sina_to_rds` 段 |
| `astock_fundamentals/ground_truth/comparator.py` | 添加 year-tier 阈值参数 |
| `astock_fundamentals/ground_truth/auto_learner.py` | 支持 2019-2022 范围 |

---

## 6. 增量测量方案

采用方案三的堆叠策略，但聚焦 2019-2022：

| 轮次 | 堆叠内容 | 预计影响 |
|------|---------|---------|
| 基线 | 当前规则集跑 2019-2022 全量对比 | 建立 BS/IS/CF 基线 |
| 轮 1 | 精确别名增量 (aliases.yaml) | ↑ BS, IS |
| 轮 2 | 值全等发现映射 (value_mapping_rules.yaml) | ↑ CF |
| 轮 3 | 行业特定规则 (金融股) | ↑ BS (银行科目) |
| 轮 4 | 科目拆分聚合 | ↑ CF 大幅提升 |
| 轮 5 | 年份段阈值微调 | ↑ 全表稳定性 |

每轮输出 BS/IS/CF 匹配率变化，写入 `data/ground_truth_reports/cleaning_progression.md`。

---

## 7. 实现优先级

1. **`rule_cleaner.py`** — 核心规则应用器，整条流水线依赖它
2. **`clean_sina_pipeline.py`** — 流水线编排脚本
3. **2019-2022 基线对比** — 跑出基线数据
4. **规则增量** — 按轮次堆叠，每轮验证
5. **Tidy Data 输出** — 最终产物

---

## 8. 待确认项 (全部已确认)

- [x] **RDS 数据覆盖范围**: 6/6 (000001/600000/600036/600519/000002/000858) 2019-2022 年 RDS 完整；后续扩展到 120 stocks（6 prefix groups × 20）后变为 1071 comparisons
- [x] **目标股票范围**: 首批 6 只验证流程 → 扩到 20 → 扩到 120 (6 prefix groups)，最终保留为 `data/ground_truth_reports/expanded_stock_list.txt`
- [x] **Tidy Data 输出路径**: 使用现有 `data/exports_v2/`，文件名 `sina_cleaned_{balance_sheet,income_statement,cash_flow}.csv`
- [x] **单位转换策略**: Sina AKShare 数据始终以元为单位，无需 unit_detection。`unit_overrides` 字段保留以备将来其他数据源

## 9. 实际产出 (vs spec)

| spec 设计 | 实际产出 |
|-----------|----------|
| 5 步骤流水线 | ✅ 全部实现，runa_clean_pipeline.py + 30 tests |
| rule_cleaner | ✅ `astock_fundamentals/ground_truth/rule_cleaner.py` 完整 |
| clean_sina_pipeline | ✅ 含 `--industries banking insurance ...` 参数 |
| 规则外置 YAML | ✅ 5 个规则文件 (aliases, value_mapping, cf_direct, industry, indirect_cf_formulas) |
| auto_learner 闭环 | ✅ `scripts/learn_clean_loop.py` 自动跑 baseline→learn→re-measure |

**最终指标** (120 stocks × 2019-2022):
- BS 99.59%
- IS 99.30%
- CF 85.64% (直接法子集)
