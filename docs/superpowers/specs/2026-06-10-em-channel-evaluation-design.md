# EM 渠道全面评估设计

**日期**: 2026-06-10
**版本**: 1.0
**作者**: Claude (brainstorming 流程)
**目标**: 评估 akshare-EM（东方财富）渠道作为 A 股财报数据主力来源的可行性

## 背景

CLAUDE.md（2026-06-10 更新）将数据渠道归纳为：
- **主力获取渠道**：akshare，其中 sina（缺间接法 CF）和 EM 两个子渠道财务数据满足分析需要
- **历史校验渠道**：RDS（2022 年前）+ 定期报告 PDF
- EM 被定性："间接法 CF 精确到分，与 RDS 完全一致"——但此结论**尚未系统验证**

现有代码库情况：
- `scripts/download_indirect_cf.py` 实际使用 `stock_financial_cash_ths`（同花顺），**不是 EM**
- `astock_fundamentals/sources/api/akshare_provider.py` 仅有 `_get_data_sina`（新浪），**没有 EM 下载器**
- `data/tmp_stocks_200.txt` 存在 200 只股票但**未按板块分布**
- 现有 `scripts/compare_indirect_cf.py` 比对 Sina/THS 与 RDS，**没有 EM 与 RDS 的对比**

本次评估需独立、可重现地验证 EM 渠道的数据质量。

## 目标

产出**结构化评估结论**回答以下问题：
1. **覆盖率**：200 只抽样股票中 EM 能下载到多少只？
2. **完整率**：下载的股票中三张表（资产负债表/利润表/现金流量表）×4 期（Q1/半年报/Q3/年报）=12 项是否齐全？
3. **数据质量**：与 RDS 比对，字段匹配率、值准确率各是多少？
4. **历史疑难改善率**：sina 渠道中无法与 RDS 匹配的数据，用 EM 重新下载后能否匹配？
5. **最终结论**：EM 是否可作为主力数据来源？

## 非目标

- 不修改生产代码（评估流水线完全独立）
- 不替代现有 Sina 渠道（仅评估）
- 不评估 PDF 年报提取（已有独立流程）
- 不评估 EM 接口的性能（仅评估数据正确性）

## 评估维度

| 维度 | 检查项 |
|------|--------|
| 完整性 | 年报、季报、半年报是否可完整下载；资产负债表、利润表、现金流量表（直接法）是否齐全 |
| 数据质量 | 与 RDS 数据逐字段比对，检查一致性 |

> **注**：EM 渠道与 Sina 一样**不提供间接法 CF**（已在 CLAUDE.md 中确认）。本次评估的"现金流量表"指直接法 CF。

## 设计

### 架构：6 个独立脚本

```
┌─────────────────────────────────────────────────────────────┐
│              EM 渠道评估流水线 (6 个脚本)                      │
├─────────────────────────────────────────────────────────────┤
│  1. eval_em_sample.py        抽样 200 只 (4板块×50)           │
│  2. eval_em_download.py      顺序下载 200只×4期×3表            │
│  3. eval_em_completeness.py  检查文件齐全性                   │
│  4. eval_em_compare_rds.py   EM vs RDS 字段比对               │
│  5. eval_em_historical.py    历史疑难数据 EM 重测             │
│  6. eval_em_report.py        汇总结构化报告                   │
└─────────────────────────────────────────────────────────────┘
```

### 数据 Schema（Tidy CSV）

遵循 CLAUDE.md 文件命名规则 `data/exports_v2/{statement_type}/{stock_code}.csv`：

```csv
stock_code,year,period,statement_type,field_code,field_name,value,display_order,source
600519,2022,annual,balance_sheet,A001N,货币资金,123456789.01,1,em
600519,2022,Q1,balance_sheet,A001N,货币资金,100000000.00,1,em
```

`period` 取值：`Q1` / `half_year` / `Q3` / `annual`
`source` 列：固定为 `em`（CLAUDE.md 数据精度规则要求标注来源）

### 目录与文件

```
scripts/
  eval_em_sample.py              # 1. 抽样
  eval_em_download.py            # 2. 下载
  eval_em_completeness.py        # 3. 完整性
  eval_em_compare_rds.py         # 4. 比对
  eval_em_historical.py          # 5. 疑难
  eval_em_report.py              # 6. 报告
data/exports_v2/em_evaluation/
  sample_200.json                # 抽样结果 (200只+板块标签)
  balance_sheet/{code}.csv       # 资产负债表
  income_statement/{code}.csv    # 利润表
  cash_flow/{code}.csv           # 现金流量表
  download_progress.json         # 断点续传
  download.log                   # 下载日志
  compare_rds_report.json        # 字段比对结果
  historical_issues.json         # 疑难样本 + EM 重测结果
docs/audit/
  2026-06-10-em-channel-evaluation.md   # 最终结构化结论
```

### 1. 抽样（eval_em_sample.py）

**输入**：
- A 股全量股票列表（从 `data/stock_list.json` 或 `data/ground_truth_reports/full_stock_list.txt` 读取）

**抽样规则**（代码前缀分类法）：
- **沪市主板**（50 只）：代码以 `600` 或 `601` 或 `603` 或 `605` 开头
- **深市主板**（50 只）：代码以 `000` 或 `001` 或 `002` 开头（**排除** 003 创业板）
- **创业板**（50 只）：代码以 `300` 或 `301` 开头
- **科创板**（50 只）：代码以 `688` 或 `689` 开头

**输出**：`data/exports_v2/em_evaluation/sample_200.json`

```json
{
  "generated_at": "2026-06-10T...",
  "seed": 42,
  "boards": {
    "sh_main": ["600000", "600001", ...],
    "sz_main": ["000001", "000002", ...],
    "chinext": ["300001", "300002", ...],
    "star": ["688001", "688002", ...]
  },
  "all_codes": ["600000", "688001", "300001", ...]
}
```

**可重现性**：`--seed 42` 固定随机种子，结果可重现。

### 2. 下载（eval_em_download.py）

**输入**：`sample_200.json`

**EM API 接口**：
- `ak.stock_balance_sheet_by_em(symbol=code)` — 资产负债表
- `ak.stock_profit_statement_by_em(symbol=code)` — 利润表
- `ak.stock_cash_flow_sheet_by_em(symbol=code)` — 现金流量表（直接法）

**下载逻辑**：
1. 对每只股票调用 3 个 API 一次（返回多年数据）
2. 筛选 2022 年 4 个报告期：
   - `2022-03-31` → period=Q1
   - `2022-06-30` → period=half_year
   - `2022-09-30` → period=Q3
   - `2022-12-31` → period=annual
3. 用 `data/decode_mappings_by_type.json` 做列名→F-code 映射
4. 输出 Tidy CSV，标记 `source=em`

**断点续传**：`download_progress.json` 记录 `{(code, period, table): done/no_data/failed}`

**重试策略**：
```python
MAX_RETRIES = 3
REQUEST_DELAY = 0.5  # 秒
backoff = 2 ** attempt
```

**错误处理**：

| 错误 | 处理 |
|------|------|
| `ConnectError`/`Timeout` | 重试 3 次，最终 `failed` |
| 空 DataFrame | `no_data`，不重试 |
| 列名不在映射表 | 跳过该字段，状态 `done`（部分数据） |
| "亿"单位后缀 | ×1e8 转换 |
| 报告期识别失败 | 跳过该行，计入 `unparsed` |

### 3. 完整性检查（eval_em_completeness.py）

**输入**：`data/exports_v2/em_evaluation/` 下的所有 CSV

**指标**：

| 指标 | 计算 | 含义 |
|------|------|------|
| **覆盖率** | 有任一 EM 数据的股票数 / 200 | EM 接口是否可用 |
| **完整率** | 12 项文件齐全的股票数 / 200 | 全量下载能力 |
| **分板块覆盖率** | 各板块有数据股票数 / 50 | 板块倾向性 |
| **分表覆盖率** | 三张表分别有数据的股票数 / 200 | 单表缺失情况 |

**输出**：
- 控制台：分板块表格
- `data/exports_v2/em_evaluation/completeness.json`

### 4. EM vs RDS 比对（eval_em_compare_rds.py）

**输入**：EM CSV + RDS（通过 `RdsLoader`）

**比对范围**：仅比对"EM 有数据且 RDS 也有数据"的对——遵循用户确认的"RDS 已有且 EM 已下载的报表一一对应后比对"。

**核心误差标准**（**绝对值 ≤ 1 元**，与 CLAUDE.md 数据精度规则一致）：

| 指标 | 定义 |
|------|------|
| **字段存在率** | EM 中存在的字段数 / RDS 期望字段数 |
| **字段匹配率** | EM 与 RDS 都存在且 \|差值\| ≤ 1.00 元的字段数 / 总比对字段数 |
| **值准确率** | 同"字段匹配率"（值差异 ≤ 1.00 元） |
| **缺失字段数** | RDS 有但 EM 没有的字段 |

**anomaly 分级**（保留供参考）：
- `perfect`: \|差值\| ≤ 0.01 元（精确到分完全相等）
- `good`: 0.01 < \|差值\| ≤ 1.00 元
- `anomaly`: \|差值\| > 1.00 元

**输出**：
- `data/exports_v2/em_evaluation/compare_rds_report.json`
- 控制台：分报表（资产负债表/利润表/现金流量表）+ 分板块 + 严重偏差字段 Top 10

### 5. 历史疑难数据 EM 重测（eval_em_historical.py）

**输入**：
- `data/exports_v2/sina_cleaned_balance_sheet.csv` / `sina_cleaned_income_statement.csv` / `sina_cleaned_cash_flow.csv`
- RDS 数据

**步骤**：
1. 扫描 sina 清洗后 CSV，找出"sina 有但与 RDS 差值 > 1 元"的字段
2. 记录为**疑难样本**：`{(stock_code, year, period, table, field_name): (sina_val, rds_val, diff)}`
3. 对每个疑难样本，调用 EM API 重新下载同一公司同一期同一字段
4. 比对 EM 值与 RDS 值
5. 计算**EM 改善率**：(EM 匹配数 - sina 匹配数) / 疑难样本数

**输出**：
- `data/exports_v2/em_evaluation/historical_issues.json`
- 控制台：sina 疑难样本数、EM 匹配数、改善率

### 6. 报告（eval_em_report.py）

**输入**：上述所有 JSON 输出

**输出**：`docs/audit/2026-06-10-em-channel-evaluation.md`

```markdown
# EM 渠道全面评估结论

## 1. 抽样覆盖性
- 总样本：200 只（沪市主板50 / 深市主板50 / 创业板50 / 科创板50）
- 覆盖率：XX% (有 EM 数据的股票数 / 200)
- 完整率：XX% (12 项文件齐全的股票数 / 200)
- 分板块覆盖率：{沪市: X%, 深市: Y%, 创业板: Z%, 科创板: W%}
- 分表覆盖率：{资产负债表: X%, 利润表: Y%, 现金流量表: Z%}

## 2. 数据质量（vs RDS）
- 比对样本数：XX 个 (股票×期次×报表)
- 字段存在率：XX% (EM 有 / RDS 期望)
- 字段匹配率：XX% (差值 ≤ 1 元的字段 / 总字段)
- 值准确率：XX% (差值 ≤ 1 元的字段 / 总字段)
- 严重偏差字段 Top 5

## 3. 历史疑难数据 EM 重测
- 疑难样本数：XX 个 (sina 与 RDS 差值 > 1 元的字段)
- EM 匹配率：XX% (EM 与 RDS 差值 ≤ 1 元的字段 / 疑难字段)
- 改善率：EM 比 sina 提升 XX 个百分点

## 4. 最终结论
- [ ] EM 可作为主力数据来源
- [ ] EM 建议作为辅助渠道（仅限 X、Y 报表）
- [ ] EM 不建议使用

## 5. 建议
- 后续行动
- 已知局限
```

## 实施步骤

| 阶段 | 脚本 | 验收 |
|------|------|------|
| M1 | `eval_em_sample.py` | 输出 `sample_200.json`，4板块各50只，可用 `--seed` 重现 |
| M2 | `eval_em_download.py` | 200只×4期×3表 全部尝试，含断点续传 |
| M3 | `eval_em_completeness.py` | 输出 `completeness.json` + 控制台表格 |
| M4 | `eval_em_compare_rds.py` | 输出 `compare_rds_report.json` + 控制台 |
| M5 | `eval_em_historical.py` | 输出 `historical_issues.json` |
| M6 | `eval_em_report.py` | 输出 `docs/audit/2026-06-10-em-channel-evaluation.md` |

**运行顺序**：
```bash
python scripts/eval_em_sample.py --seed 42
python scripts/eval_em_download.py              # 顺序下载 ~30-60min
python scripts/eval_em_completeness.py
python scripts/eval_em_compare_rds.py
python scripts/eval_em_historical.py
python scripts/eval_em_report.py
```

## 依赖

**复用现有**：
- `astock_fundamentals.sources.rds.RdsLoader`
- `astock_fundamentals.ground_truth.comparator`
- `data/decode_mappings_by_type.json`
- `data/stock_list.json` 或 `data/ground_truth_reports/full_stock_list.txt`

**新增**：
- `akshare >= 1.12.0`（已安装）
- 仅使用 `stock_balance_sheet_by_em` / `stock_profit_statement_by_em` / `stock_cash_flow_sheet_by_em`

**对生产代码的影响**：0 处修改

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| AKShare EM 接口可能在某些股票上不稳定 | 3 次重试 + 断点续传，失败计入 `failed` 状态 |
| AKShare EM 接口名/参数可能有版本差异 | M2 实施前先抽样 5 只股票验证可行性 |
| RDS 数据不全（2022 年报可能在 RDS 边缘） | 比对仅对"双方都有数据"的对，跳过单边缺失 |
| 中文列名变更（AKShare 升级） | 复用现有 `decode_mappings_by_type.json`，缺失列记录到日志 |
| 200 只抽样后股票数与板块预期不符 | 抽样后立即统计各板块数量，不足则补抽 |
| 间接法 CF 缺失（EM 不提供） | 本次评估仅评估直接法 CF，与 sina 渠道对比时也仅以直接法为基线 |

## 验收标准

**完成的定义**：
1. `docs/audit/2026-06-10-em-channel-evaluation.md` 文件存在且结构完整
2. 报告包含 4 个核心指标（覆盖率、完整率、匹配率、改善率）
3. 报告给出明确最终结论（3 选 1）
4. 所有数据可追溯（`sample_200.json` 固定 seed 可重现抽样）
5. 所有 6 个脚本独立可运行

## 预估时间

- M1 抽样：< 1 分钟
- M2 下载：30-60 分钟（200×4×3=2400 次 API 调用，0.5s 间隔）
- M3-M6 处理：每步 < 5 分钟
- **总计**：约 1-1.5 小时
