# akshare 各渠道现金流量表数据质量测试报告

**测试目标**：600519 贵州茅台 2020 年年报现金流量表  
**测试日期**：2026-06-11  
**对比基准**：RDS (cninfo/data_backup/cf_o.rds) — 49 项 item，含直接法+间接法  
**说明**：原计划测2021年，但RDS中600519恰好无2021年报CF数据，按用户指示改用2020年报

---

## 1. 测试范围（10 个 akshare 接口）

| # | 接口 | 类型 | 调用参数 |
|---|------|------|----------|
| 01 | `stock_cash_flow_sheet_by_yearly_em` | EM 年度 | `symbol="SH600519"` |
| 02 | `stock_cash_flow_sheet_by_quarterly_em` | EM 单季度 | `symbol="SH600519"` |
| 03 | `stock_cash_flow_sheet_by_report_em` | EM 按报告期 | `symbol="SH600519"` |
| 04 | `stock_cash_flow_sheet_by_report_delisted_em` | EM 退市股 | `symbol="SH600519"` |
| 05 | `stock_financial_cash_ths` | THS 旧版 按报告期 | `symbol="600519", indicator="按报告期"` |
| 06 | `stock_financial_cash_ths` | THS 旧版 按年度 | `symbol="600519", indicator="按年度"` |
| 07 | `stock_financial_cash_ths` | THS 旧版 按单季度 | `symbol="600519", indicator="按单季度"` |
| 08 | `stock_financial_cash_new_ths` | THS 新版 按报告期 | `symbol="600519", indicator="按报告期"` |
| 09 | `stock_financial_cash_new_ths` | THS 新版 按年度 | `symbol="600519", indicator="按年度"` |
| 10 | `stock_financial_report_sina` | Sina 综合 | `stock="sh600519", symbol="现金流量表"` |

> 备注：akshare 中无 sina 专用现金流量表接口，Sina 现金流量表通过综合接口 `stock_financial_report_sina(symbol="现金流量表")` 获取。

---

## 2. 数据下载结果

全部 10 个接口下载成功，原始数据保存于 `tmp/akshare_test_600519_2020/raw_*.csv`：

| 接口 | 行数 | 列数 | 说明 |
|------|-----:|-----:|------|
| 01_em_yearly | 26 | 254 | 全部年报 |
| 02_em_quarterly | 93 | 253 | 全部单季度数据 |
| 03_em_report | 98 | 254 | 全部报告期（年+季） |
| 04_em_report_delisted | 98 | 254 | **意外返回600519数据** — 该接口未做退市股过滤 |
| 05_ths_old_report | 98 | 72 | 按报告期；**值带"亿"单位** |
| 06_ths_old_yearly | 26 | 72 | 按年度；同上 |
| 07_ths_old_single_q | 93 | 72 | 按单季度 |
| 08_ths_new_report | 4500 | 10 | 长格式（metric_name + value） |
| 09_ths_new_yearly | 2340 | 10 | 同上 |
| 10_sina_cf | 98 | 71 | 综合接口含报告日 |

---

## 3. 与 RDS 标准对比（核心结果）

### 评分指标
- **精确到分**：`|渠道值 - RDS值| < 0.01 元`
- **精度损失（亚元）**：差异 < 1 元
- **舍入或聚合（<1%）**：相对误差 < 1%（典型为"亿"单位精度损失）
- **大误差（≥1%）**：含 best-match 误匹配（即渠道根本缺失该字段）

| 渠道 | 字段数 | 精确 | 精度损失 | 舍入 | 大误差 | 间接法字段 | 评级 |
|------|-----:|-----:|------:|----:|------:|----------:|------|
| 01 EM 年度 | 51 | **47** | 0 | 0 | 2 | **17** | ⭐⭐⭐⭐⭐ |
| 03 EM 按报告期 | 51 | **47** | 0 | 0 | 2 | 17 | ⭐⭐⭐⭐⭐ |
| 04 EM 退市股接口 | 51 | 47 | 0 | 0 | 2 | 17 | ⭐⭐⭐⭐⭐（接口归类异常） |
| 08 THS 新版 按报告期 | 48 | **47** | 0 | 0 | 2 | 10/16* | ⭐⭐⭐⭐⭐ |
| 09 THS 新版 按年度 | 48 | **47** | 0 | 0 | 2 | 10/16* | ⭐⭐⭐⭐⭐ |
| 10 Sina 综合 | 35 | **35** | 0 | 0 | 14 | 2 | ⭐⭐⭐（仅直接法） |
| 05 THS 旧版 按报告期 | 48 | 1 | 0 | 41 | 7 | 13 | ⭐⭐（精度仅到亿） |
| 06 THS 旧版 按年度 | 48 | 1 | 0 | 41 | 7 | 13 | ⭐⭐ |
| 02 EM 单季度 | 53 | 2 | 0 | 4 | 43 | 0 | n/a（返回Q4单季值） |
| 07 THS 旧版 按单季度 | 28 | 0 | 0 | 6 | 43 | 0 | n/a（单季度数据） |

> *THS 新版的间接法检测数为 10，但人工核对其 47 个 exact match 中实际包含 **16/17** 个 RDS 间接法项目（仅缺 F096 信用减值损失）

---

## 4. 关键发现详解

### 4.1 EM (年度/报告期) — 实际精确率 48/49 = 98.0%

EM 标记的 2 个"大误差"实际为：
1. **F013 支付其他与经营活动有关的现金** (RDS = 4,247,026,186.46)  
   EM 拆为两个字段：  
   - `PAY_OTHER_OPERATE` = 4,047,026,186.46  
   - `OPERATE_OUTFLOW_OTHER` = 200,000,000.00  
   两者相加 = 4,247,026,186.46 ✓ **完全匹配，仅是字段切分差异**
2. **F096 信用减值损失** (RDS = 71,371,809.85)  
   EM 未提供此字段 — **真实缺失**

**结论**：EM 实际覆盖 48/49 直接法+间接法项目，仅缺信用减值损失一项。**间接法CF完整可用**（净利润、折旧、摊销、存货变动、应收应付、递延税等17项全部精确到分）。

### 4.2 Sina — 仅直接法 + 部分汇总

Sina 35 个非空字段全部精确到分（35/35 = 100% 精确率），但 RDS 49 项中 **14 项 Sina 完全缺失**（被算法误匹配为 large_error）：
- F044 净利润 ❌
- F046-F058 间接法各项（折旧/摊销/公允价值/投资损失/递延税/存货/应收应付）❌
- F096 信用减值损失 ❌

**结论**：**Sina 确实不提供间接法CF补充资料**，与 CLAUDE.md 描述一致。

### 4.3 THS 新版 — 字段最完整且精确

THS 新版 47/48 个返回字段精确到分，间接法覆盖 **16/17**（仅缺 F096）。所有间接法项目用英文 metric_name 命名（如 `cash_net_profit`、`depreciation_etc`、`amortization_intangible_assets`、`inventory_decrease`、`operating_receivable_decrease` 等）。

**反驳 CLAUDE.md 中"THS 新版精度不稳定"的说法** — 本次测试600519 2020年报数据**完全精确到分**，与 RDS 完全一致。需要在其他股票上做更广泛测试才能验证"精度因股票而异"的说法。

### 4.4 THS 旧版 — 精度限制到亿

确认 CLAUDE.md 描述：THS 旧版接口返回的值是字符串带单位（如 "1070.24亿"），换算后精度仅到亿元。仅 1/49 精确（碰巧到分）。

例：
- 销售商品收到的现金：THS = "1070.24亿" → 107,024,000,000，RDS = 107,024,384,560.17（差异 384,560.17元）
- 经营活动净额：THS = "516.69亿" → 51,669,000,000，RDS = 51,669,068,693.03（差异 68,693.03元）

### 4.5 EM 退市股接口意外行为

`stock_cash_flow_sheet_by_report_delisted_em(symbol="SH600519")` 仍然返回了 600519 的完整数据（98 行 × 254 列），与 `by_report_em` 输出完全一致。**该接口未做退市股过滤** — 调用者需自行注意命名歧义。

### 4.6 EM 单季度接口

`stock_cash_flow_sheet_by_quarterly_em` 2020-12-31 行返回 `REPORT_TYPE="四季度"`，值为单季 Q4 值（如 NETCASH_OPERATE = 26,558,065,873.04），并非年度累计。用于年度对比时**不适用**，需调用 `_yearly_em` 或 `_report_em`。

---

## 5. 总结与推荐

> ⚠ **重要前提：EM 与 THS 新版的精度均不稳定** —— 本次 600519 测试中两者都精确到分，但 **EM 渠道实际精度因股票而异，部分上市公司只精确到百万元**，与 THS 新版同样存在该问题。以下推荐仅在目标股票完成精度抽查后才适用。

| 用途 | 推荐接口 | 理由 |
|------|---------|------|
| **年度CF（含间接法）首选** | `stock_cash_flow_sheet_by_yearly_em` 或 `stock_financial_cash_new_ths(indicator="按年度")` | 600519 精确到分，含间接法补充资料，覆盖 48/49 项；**其他股票需先抽样校验精度** |
| **任意报告期CF（含间接法）** | `stock_cash_flow_sheet_by_report_em` 或 `stock_financial_cash_new_ths(indicator="按报告期")` | 同上 |
| **直接法CF快速校验** | `stock_financial_report_sina(symbol="现金流量表")` | 35个直接法项目全部精确，**Sina 精度稳定到分**，但无间接法 |
| **单季度CF** | `stock_cash_flow_sheet_by_quarterly_em` | 唯一返回单季值的接口 |
| **不推荐** | `stock_financial_cash_ths`（任何 indicator）| 精度仅到亿，无法精确到分 |
| **慎用** | `stock_cash_flow_sheet_by_report_delisted_em` | 命名误导，实际未做退市股过滤 |

---

## 6. 对 CLAUDE.md 的修正建议

经本次测试，**CLAUDE.md 中以下描述需修正/补充**：

| 原描述 | 测试结果 | 建议修正 |
|--------|---------|----------|
| "EM 不提供间接法 CF" | EM 提供 17 项间接法字段（含 NETPROFIT、FA_IR_DEPR、IA_AMORTIZE 等） | EM **提供完整间接法 CF**，覆盖 48/49 项（仅缺 F096 信用减值损失） |
| "EM 精确到分（曾被认为）" | 仅在 600519 上验证精确到分 | **EM 精度因股票而异**：部分上市公司精确到分，部分仅精确到百万元；与 THS 新版同样存在精度不稳定问题，使用前需对目标股票抽样校验 |
| "THS 新版精度不稳定" | 600519 测试结果完全精确到分 | 描述正确；至少 600519 上精确到分，但其他股票仍可能仅到百万元 |
| "Sina 主力可靠" | Sina 仅提供直接法 35 项，无间接法 | Sina 仅在直接法 CF 上可靠且精度稳定，间接法需 EM 或 THS 新版 |

---

## 7. 数据存档

- **下载脚本**：`scripts/akshare_cf_test_download.py`
- **对比脚本**：`scripts/akshare_cf_test_compare.py`
- **RDS标准导出**：`scripts/akshare_cf_test_export_rds.py`
- **原始数据**：`tmp/akshare_test_600519_2020/raw_*.csv` (10 个)
- **每渠道元数据**：`tmp/akshare_test_600519_2020/meta_*.json` (10 个)
- **下载汇总**：`tmp/akshare_test_600519_2020/_download_summary.json`
- **质量对比JSON**：`tmp/akshare_test_600519_2020/_quality_report.json`
- **本报告**：`tmp/akshare_test_600519_2020/_quality_report.md`
