# peri_rept_down - Claude Code 指令

## 项目概述

A股上市公司财务数据多源清洗流水线。从Sina(AKShare)、RDS(cninfo)、PDF年报等数据源获取财务数据，通过规则引擎清洗为统一的Tidy Data。

## 关键规则

### 1. 指令执行规则

**当发现按照用户的具体指令无法完成任务时，必须向用户汇报限制并询问处理方式，不得擅自切换方案。**

例如：用户要求"通过Sina渠道下载间接法CF数据"，但Sina渠道不提供该数据时，应报告"Sina渠道不提供间接法CF数据，现有替代方案是X/Y/Z，请问如何处理？"，而不是自行切换到同花顺(THS)接口。

### 2. 数据渠道结论（2026-06-11 多股测试更新）

本项目数据渠道结构：

| 渠道 | 数据范围 | 优点 | 缺点 |
|------|----------|------|------|
| RDS (cninfo) | **仅 2022 年之前** | 数据质量高，可作 2022 前的金标准 | 不再更新；部分股票 2021 年报也已缺失（如 600519 cf_o.rds 最新到 2020-12-31）|
| 上市公司定期报告 (PDF) | 全量 | 权威性最高；**2022 年之后唯一独立校验源** | ①提取规则导致错漏；②退市公司可能无法下载历史财报 |
| akshare（主力下载渠道） | 全量、免费 | 国内主要数据源；多接口可交叉印证 | **精度因股票而异**，需独立校验 |

#### akshare 子渠道质量评级（2026-06-11 多股测试结论）

**测试样本**：5 只股票 × 5 渠道，涵盖上海主板/深圳主板/上海科创板/深圳创业板。详见 `tmp/akshare_test_multi_stocks_2020/_multi_stocks_report.html`。

| 接口 | 精确率范围 | 是否提供间接法 | 推荐用法 |
|------|---------:|------------:|---------|
| `stock_cash_flow_sheet_by_yearly_em` | 0–100% | ✓ 17项完整 | 年报首选下载渠道之一 |
| `stock_cash_flow_sheet_by_report_em` | 0–100% | ✓ 同上 | 任意报告期首选 |
| `stock_financial_cash_new_ths(indicator='按年度')` | 0–100% | ✓ 16/17项 | 与 EM 交叉印证 |
| `stock_financial_cash_new_ths(indicator='按报告期')` | 0–100% | ✓ 同上 | 同上 |
| `stock_financial_report_sina(symbol='现金流量表')` | 100% (但仅35项) | **✗ 缺间接法** | 直接法快速校验，精度稳定 |
| `stock_cash_flow_sheet_by_quarterly_em` | n/a（返回单季值） | — | 仅适合季度分析 |
| `stock_cash_flow_sheet_by_report_delisted_em` | 同 by_report_em | ✓ | **不推荐**：命名误导，对金融股直接报错 |
| `stock_financial_cash_ths`（旧版） | 1/49 精确到分（仅到亿）| △ 13项 | **不推荐**：精度仅到亿元 |

#### ⚠ 关键发现：精度因股票而异

- **000651 格力电器** / **600887 伊利股份**：EM/THS 新版精确到分（98–100%）
- **300750 宁德时代**：EM 与 THS 新版**全部降级到百元精度**（精确率 0%，差异 0–50 元）
- **600036 招商银行**（金融股）：精确率 78–90%，`em_delisted` 直接报错
- **688981 中芯国际**（科创板）：RDS 本身只到千元，akshare 同步

**结论**：所谓"多渠道互相印证"只能确认渠道间一致性，**无法替代独立标准对绝对值的校验**。

### 3. 数据获取与校验策略

#### 2022 年及之前
1. **主力下载**：EM yearly + THS new yearly **双跑**，遇到不一致就标红
2. **金标准校验**：RDS (`cf_o.rds` / `cf_f.rds`)
3. **辅助校验**：PDF 年报提取

#### 2022 年之后（RDS 失效）
1. **主力下载**：EM yearly + THS new yearly **双跑**
2. **唯一独立校验源**：**PDF 年报提取**（无 RDS 可用）
3. **每只股票必须打"精度等级"标签**：精确到分 / 千元 / 百元 / 亿元
4. **不能依赖单一渠道的"互相印证"作为终审**

#### 间接法现金流量表
- Sina **不提供**间接法 CF（仅 35 项直接法）
- EM 与 THS 新版**提供** 17 项完整间接法（但精度同样不稳定）
- THS 旧版精度仅到亿，不可用
- PDF 年报是**绝对**可靠的间接法 CF 源（提取规则需持续改进）

### 4. 数据源优先级

| 优先级 | 数据源 | 说明 |
|--------|--------|------|
| 1 | RDS (cninfo) | 2022 前金标准，**仅校验用** |
| 1 | PDF 年报 | 权威性最高，**2022+ 唯一独立校验源** |
| 2 | akshare-EM (`stock_cash_flow_sheet_by_*_em`) | 主力下载，含间接法，**精度因股票而异需校验** |
| 2 | akshare-THS新版 (`stock_financial_cash_new_ths`) | 主力下载，含间接法，**与 EM 双跑印证** |
| 3 | akshare-Sina (`stock_financial_report_sina`) | 直接法快速校验，**精度稳定到分**但**无间接法** |
| ✗ | akshare-THS旧版 (`stock_financial_cash_ths`) | 精度仅到亿，**不可用** |
| ✗ | `stock_cash_flow_sheet_by_report_delisted_em` | 命名误导 + 金融股报错，**不推荐** |
| ✗ | `stock_cash_flow_sheet_by_quarterly_em` | 仅返回单季值，不适合年度对比 |

### 5. 数据精度要求

- **目标精度**：精确到元，小数点后2位（分）
- **每只股票必须**先校验精度等级（与 RDS 或 PDF 对比抽样）后再判断该股票数据是否可用
- 数据来源**必须**在 CSV 中标注 `source` 列，**应额外标注 `precision_tier` 列**（fen/qian/wan/baiwan/yi）

### 6. 文件命名规则

- 下载脚本：`scripts/download_{data_source}_{statement_type}.py`
- 数据输出：`data/exports_v2/{statement_type}/{stock_code}.csv`
- 对比报告：`docs/audit/YYYY-MM-DD-{topic}.md`
- 临时测试数据：`tmp/{test_name}/`

### 7. Git 提交规则

- 每次提交必须有清晰的 commit message
- 数据文件和脚本文件分开提交
- 规则变更必须附带测试验证

### 8. 测试数据归档

- `tmp/akshare_test_600519_2020/`：第一次单股 10 渠道全量测试（2026-06-11）
- `tmp/akshare_test_multi_stocks_2020/`：第二次 5 股 × 5 渠道精度稳定性测试（2026-06-11）
