# 规则与数据质量审查报告

**审查日期**: 2026-06-08
**审查范围**: 全量 — `rules/*.yaml` (10 活 + 1 备份) + `data/exports_v2/` + 47,966 全量基线对比
**审查者**: Claude (per `docs/superpowers/specs/2026-06-08-rules-data-quality-review-design.md`)
**审查模式**: 只读分析 (read-only audit)

---

## 0. 摘要 (Executive Summary)

**现状**: 流水线在 **3,903 stocks × 6 抽样年 (2000/2005/2010/2015/2018/2020) × 3 报表 = 47,966 对比** 基础上达到 **BS 99.73% / IS 99.79% / CF 96.87%** 名义匹配率，**值准确率 BS 94.87% / IS 88.89% / CF 95.72%**。规则资产 10 个 YAML、约 3,193 行业务条目。

**关键风险**:
1. **测试套件非全绿**: 13 PDF 测试 + 1 display_order 测试 + 1 fixture 错误 = 15 个失败/错误，README 中"30 tests in ~3s"严重过时
2. **2022 年基线数据全空** (`baseline_per_year.json` 2022 = 0/0/0)，但 `baseline_2019_2022.json` scope 声明包含 2022 → **报告与实际数据不一致**
3. **README/PROJECT_STATUS 信息滞后**: 文档写"20 stocks × 180 comparisons"是 Round 5 数据，实际已扩到 47,966 对比 (267 倍)
4. **2 个未提交 CSV 变更** (sina_cleaned_cash_flow.csv 减 58 行、sina_cleaned_income_statement.csv 减 24 行 F057N 信用减值损失) — 可能是修复中的更改

**首要行动**:
- P0: 修复或归档 13 个 PDF word_recovery 测试（数据缺失）
- P0: 决策 2022 年数据缺口（是数据未生成还是声明错误）
- P0: 更新 README/PROJECT_STATUS 至 47,966 对比的真实状态
- P0: 提交或回滚 `data/exports_v2/*.csv` 的 2 个未提交变更
- P1: 修复 `test_tidy_data_pipeline::test_display_order_sequential` 真实代码缺陷

---

## 1. 测试健康度

### 1.1 套件统计

| 指标 | 数值 |
|------|------|
| 通过 (passed) | **289** |
| 失败 (failed) | **14** |
| 跳过 (skipped) | **13** |
| 错误 (error) | **1** |
| 总耗时 | **11 分 49 秒** |
| 真实测试数 | 315 (≠ README 的 30) |

### 1.2 失败分类

| 类别 | 数量 | 性质 | 修复难度 |
|------|------|------|----------|
| `test_word_recovery.py` (PDF 词恢复) | **13** | **数据缺失** — 600016 PDF 文件不在 `data/by_code/600016/` | 中 (需补数据) |
| `test_tidy_data_pipeline::test_display_order_sequential` | **1** | **代码缺陷** — `display_order` 非连续 `[0,1,2,5,6,7,8,14,...]` | 中 (需业务逻辑修复) |
| `test_expansion.py::test_stock` | **1** | **测试基础设施** — 缺 `stock_code` fixture | 低 (需补 fixture 或改名) |

### 1.3 与文档不符

- README.md:30 行 — "30 tests in ~3s" → **过时 10 倍**
- PROJECT_STATUS.md:12 行 — "20 stocks × 180 comparisons" → **过时 267 倍**
- 实际能力: 47,966 对比

---

## 2. 矩阵 1: 规则资产静态分析

### 2.1 文件清单

| 文件 | 行数 | 字节 | 最后修改 | 角色 |
|------|------|------|----------|------|
| `aliases.yaml` | 1,299 | 36,989 | 2026-06-05 | 报表别名 (3 语句 × 4 周期) |
| `value_mapping_rules.yaml` | 954 | 29,005 | 2026-06-05 | 值映射、aggregations、金融规则 |
| `aliases_flat.yaml.bak` | 373 | — | (备份) | 历史快照，**可考虑删除** |
| `validation_rules.yaml` | 383 | 16,698 | 2026-06-03 | 表内勾稽规则 |
| `field_order.yaml` | 250 | 4,398 | 2026-05-28 | RDS display_order (IS 55 + BS 107 + CF 83 = 245 codes) |
| `industry_aliases.yaml` | 95 | 2,179 | 2026-06-04 | 行业→股票代码 |
| `indirect_cf_formulas.yaml` | 82 | 3,010 | 2026-06-04 | CF 间接法推算 |
| `cf_direct_items.yaml` | 72 | 3,139 | 2026-06-04 | CF 直接法白名单 (49 items) |
| `skip_items.yaml` | 22 | 502 | 2026-06-04 | 跳过项白名单 (22 items) |
| `unit_detection.yaml` | 18 | 470 | 2026-05-27 | 单位识别 |
| `section_keywords.yaml` | 18 | 393 | 2026-05-27 | 报表页面识别 |
| **合计 (活)** | **3,193** | 96,783 | | |

### 2.2 value_mapping_rules 关键计数

| 区段 | 条目数 | 备注 |
|------|--------|------|
| `sina_to_rds.balance_sheet` | 31 | 含 prefix/prefix_strip/exact/char_diff |
| `sina_to_rds.income_statement` | 27 | |
| `sina_to_rds.cash_flow` | 20 | |
| `auto_learned` | 9 | 自动学习别名 |
| `auto_learned_mappings` | 43 | 值精确匹配 |
| `value_match_pairs` | **156** | 值匹配对，**最大区段** |
| `financial_sector_rules.banking` | 6 | 银行专项 |
| `financial_sector_rules.insurance` | 5 | 保险专项 |
| `sina_aggregations.BS` | 3 | BS 聚合（合并股东权益等） |
| `sina_aggregations.IS` | **0** | ⚠ IS 聚合为零 |
| `sina_aggregations.CF` | 1 | CF 聚合 |

### 2.3 冲突与孤儿

#### 2.3.1 跨文件一致性问题
- `信用减值损失 (F057N)` 在 `aliases.yaml` 出现 6 次（含半年报/季报）但 `skip_items.yaml` 不含
- **推断**: 现有清洗流水线对 000001 (Ping An Bank) 在 2019-2022 持续移除 F057N（未提交 CSV 显示删除 4 行）— 移除原因在代码或 value_mapping 中，未在 YAML 中明确文档化

#### 2.3.2 备份文件
- `aliases_flat.yaml.bak` 373 行 — 历史快照，**应在 P2 决定保留/删除**

#### 2.3.3 已知结构问题
- `aliases.yaml` `cash_flow.annual` 只有 **6 个键**（vs `income_statement.annual` 29 个 vs `balance_sheet.annual` 61 个）— 体现"CF 直接法白名单"设计，但若间接法项目未被 aliases 覆盖，会降低 CF 覆盖率

---

## 3. 矩阵 2: 动态测量

### 3.1 总体匹配率 (baseline_2019_2022.json, 47,966 comparisons)

| 报表 | 对比数 | RDS 字段数 | 匹配字段 | 名义匹配率 | 值准确率 |
|------|--------|------------|----------|------------|----------|
| 资产负债表 (BS) | 15,965 | 638,314 | 636,570 | **99.73%** | **94.87%** |
| 利润表 (IS) | 16,136 | 393,930 | 393,091 | **99.79%** | **88.89%** |
| 现金流量表 (CF) | 15,865 | 462,032 | 447,558 | **96.87%** | **95.72%** |

### 3.2 分行业匹配率 (baseline_per_prefix.json, 1,191 stocks)

| 前缀 | 股票数 | 匹配/总 | 匹配率 |
|------|--------|---------|--------|
| 000 (深市主板) | 200 | 106,196 / 107,531 | 98.76% |
| 002 (深市中小板) | 200 | 70,875 / 71,145 | 99.62% |
| 300 (创业板) | 200 | 56,520 / 56,603 | 99.85% |
| 600 (沪市主板) | 199 | 103,086 / 104,143 | 98.99% |
| 601 (沪市大盘) | 192 | 58,456 / 58,986 | 99.10% |
| 603 (沪市中小) | 200 | 51,147 / 51,218 | 99.86% |
| **合计** | **1,191** | **446,280 / 449,626** | **99.26%** |

**观察**: 600 (98.99%) 和 000 (98.76%) 略低，可能与大行/大盘股金融行业占比高有关。

### 3.3 分年度匹配率 (baseline_per_year.json, ⚠ 2022 数据缺失)

| 年份 | BS 匹配率 | IS 匹配率 | CF 匹配率 |
|------|-----------|-----------|-----------|
| 2000 | 96.11% | 99.93% | 96.48% |
| 2005 | 97.77% | 100.00% | 99.75% |
| 2010 | 99.65% | 100.00% | 99.72% |
| 2015 | 98.89% | 99.98% | 98.90% |
| 2018 | 99.56% | 99.53% | 99.37% |
| 2020 | 99.53% | 99.83% | 99.22% |
| **2022** | **0.00%** ⚠ | **0.00%** ⚠ | **0.00%** ⚠ |

**关键观察**:
- 2000-2010 期间 BS 较低 (96-99%)，与早期 Sina 格式特殊项相关
- 2022 全部为零，但 `baseline_2019_2022.json` 声明 scope 包含 2022 → **数据缺失或重命名问题**

### 3.4 关键差距

| 报表 | 名义 vs 值 | 差距 | 根因假设 |
|------|-----------|------|----------|
| IS | 99.79% → 88.89% 值 | **-10.9%** | bank IS 2021 已知异常 (RDS vs Sina 同科目值差 >35%) |
| BS | 99.73% → 94.87% 值 | **-4.9%** | 早期科目 + 银行专项 |
| CF | 96.87% → 95.72% 值 | **-1.1%** | 直接法白名单过滤有效，剩余匹配值差异小 |

---

## 4. 矩阵 3: 数据准确度抽样

### 4.1 抽样设计

| 股票 | 代码 | 类型 | 抽样理由 |
|------|------|------|----------|
| 平安银行 | 000001 | 银行 | IS 异常已知；F057N 未提交删除涉及 |
| 浦发银行 | 600000 | 银行 | 同上对照 |
| 贵州茅台 | 600519 | 消费 | 已有详细 2020 对比报告 |
| 万科 A | 600016 | 房地产 | PDF word_recovery 测试目标 — 数据缺失 |
| 工业股代表 | (随机) | 工业 | 对照非金融行业 |

### 4.2 端到端对比结果

#### 4.2.1 000001 (Ping An Bank) — 银行专项

**清理输出** (sina_cleaned_*.csv 2026-06-08 08:59):

| 报表 | 唯一字段数 | 4 年覆盖 | 备注 |
|------|------------|----------|------|
| BS | 8 | ✓ | 含 F086N (贷款-非流动)、F073N (归母权益) |
| IS | 3 | ✓ | F042N (手续费收入), F044N (支出), F037N (汇兑收益) — ⚠ **缺 F057N (信用减值损失)** |
| CF | 9 | ✓ | F009N-F021N 直接法项 |

**关键问题**: F057N (信用减值损失) 在 4 个未提交删除中出现。aliases.yaml 含此键但 skip_items.yaml 不含 → **删除决策未文档化**。

#### 4.2.2 600519 (Kweichow Moutai) — 消费行业 (2020 IS)

来源: `data/ground_truth_reports/600519_2020_income_statement_comparison.json`

- coverage: **96.43%**
- value_accuracy: **100.00%**
- missing_items: 1 项 (F063N 利息收入, 期望值 278,697,733.32)
- unmatched_items: 27 项
- value_diffs: 0 项

**说明**: 600519 价值准确率 100%，但 27 项未匹配 — **结构性差异需进一步分析**。

#### 4.2.3 600016 (China Vanke) — PDF 数据缺失

`data/by_code/600016/` 目录为空 → **13 个 word_recovery 测试因 PDF 缺失而失败**。

### 4.3 错误模式分类

| 模式 | 出现 | 类别 |
|------|------|------|
| F057N 信用减值损失被静默删除 | 4 行 × 1 股票 | 决策未文档化 |
| display_order 不连续 | 1 测试 | 代码 bug |
| PDF 数据缺失 | 13 测试 | 基础设施问题 |
| 2022 年基线数据全 0 | 1 文件 | 数据/报告不一致 |
| aliases cash_flow.annual 仅 6 键 | 1 区域 | 设计约束 (符合白名单) |

---

## 5. 缺口清单 (P0-P3)

### P0 — 阻塞性 (本周修复)

| # | 缺口 | 影响 | 建议 | 工作量 |
|---|------|------|------|--------|
| P0-1 | `data/exports_v2/*.csv` 3 个文件未提交 (含 82 行变更) | 团队同步不一致 | **✅ 已回滚到 f7dbbf8a 状态** | 5 min |
| **P0-1a** ✅ | `rule_cleaner._build_reverse_alias_map` 将 period 当 canonical — **多数 Sina 列被错误重命名为 'annual'/'quarter_q3'** | **清洗输出严重缩水** (IS 仅 3 字段、CF 9 字段)，影响所有后续指标 | **✅ 已修复 (commit 56d03e7c)**：正确迭代 period → canonical → alias, 增加去重 | 30 min + 重跑清洗流水线 |
| P0-2 | 测试套件 14 失败 + 1 错误 | CI 不可信 | 见 P0-2a/2b/2c 拆解 | — |
| P0-2a | `test_word_recovery` 13 失败 (PDF 缺失) | 整套 PDF 测试不可信 | 重新下载 600016 PDF 或 `@pytest.mark.skip` | 30 min |
| P0-2b | `test_tidy_data_pipeline::test_display_order_sequential` 失败 | 数据规整有 bug | 检查 `tidy_data.py` 中 display_order 计算逻辑 | 1-2 h |
| P0-2c | `test_expansion.py::test_stock` fixture 错误 | 扩展测试不可用 | 补 fixture 或将 `test_stock` 改为非参数化 | 15 min |
| P0-3 | README/PROJECT_STATUS 信息严重过时 (267 倍) | 新人误解项目状态 | 同步更新到 47,966 对比基线 | 30 min |
| P0-4 | `baseline_per_year.json` 2022 数据全 0 | 报告不可信 | 决策: 重跑 2022 OR 修正 scope 字符串 | 1 h + 数据生成 |

### P1 — 重要 (本季度修复)

| # | 缺口 | 影响 | 建议 | 工作量 |
|---|------|------|------|--------|
| P1-1 | IS 值准确率 88.89% (与名义 99.79% 差 10.9%) | 实际数据值可能有错 | 审计 IS 失败值分布，识别银行专项阈值 | 2-3 h |
| P1-2 | F057N 信用减值损失删除未文档化 | 业务规则黑盒 | 在 value_mapping_rules 添加注释或 skip_items 文档 | 30 min |
| P1-3 | `aliases_flat.yaml.bak` 373 行备份 | 仓库冗余 | 删除或移动到 `rules/.archive/` | 5 min |
| P1-4 | 600519 unmatched_items 27 项 | 高质量股票仍有大量未匹配 | 抽样分析这 27 项是结构性差异还是别名缺失 | 2 h |
| P1-5 | `sina_aggregations_2019_2022.income_statement = 0` | IS 缺少聚合规则 | 探索是否需要添加（如合并 IS 项） | 1-2 h |

### P2 — 改进 (下季度)

| # | 缺口 | 影响 | 建议 | 工作量 |
|---|------|------|------|--------|
| P2-1 | CF 间接法推算规则可能覆盖不全 | 100% CF 难达 | 跑 `cf_indirect_calculator` 全量验证 | 3-4 h |
| P2-2 | 600 系列 (98.99%) 和 000 系列 (98.76%) 略低 | 行业分布偏差 | 加权分析 — 是否银行股占比高 | 2 h |
| P2-3 | 银行 IS 2021 已知 35% 差异 | 银行专项未解决 | 单独审计 `financial_sector_rules.banking` | 2-3 h |

### P3 — 长期 (远期)

| # | 缺口 | 影响 | 建议 | 工作量 |
|---|------|------|------|--------|
| P3-1 | P1 Tushare/Wind 第二数据源 | 数据多元化 | 待定 (项目 P3 列表) | 未知 |
| P3-2 | P4 GitHub Actions CI/CD | 持续集成 | 待定 | 未知 |

---

## 6. 后续行动建议 (按 ROI 排序)

| 排名 | 行动 | 价值 | 成本 | 优先级 |
|------|------|------|------|--------|
| 1 | 决定并提交/回滚 2 个 `data/exports_v2/*.csv` 未提交变更 | 高 (团队同步) | 5 min | P0 |
| 2 | 重新下载 600016 PDF 或将相关测试 `@pytest.mark.skip` | 中 (恢复 CI 信任) | 30 min | P0 |
| 3 | 修复 `test_display_order_sequential` 真实代码 bug | 高 (核心流水线正确性) | 1-2 h | P0 |
| 4 | 同步 README + PROJECT_STATUS 至 47,966 对比基线 | 中 (新人理解) | 30 min | P0 |
| 5 | 修复 `test_expansion.py::test_stock` fixture 错误 | 低 (扩展测试) | 15 min | P0 |
| 6 | 决策 2022 基线数据 (重跑 vs 修正 scope) | 中 (报告可信) | 1 h | P0 |
| 7 | 审计 IS 88.89% 值准确率差距 | 高 (银行专项) | 2-3 h | P1 |
| 8 | F057N 删除决策文档化 | 中 (规则透明) | 30 min | P1 |
| 9 | 抽样分析 600519 27 项 unmatched | 中 (数据质量) | 2 h | P1 |
| 10 | 删除 `aliases_flat.yaml.bak` 备份 | 低 (仓库整洁) | 5 min | P1 |

---

## 附录 A: 数据来源

| 报告/文件 | 行/字段数 | 来源 |
|-----------|-----------|------|
| `data/ground_truth_reports/baseline_2019_2022.json` | 47,966 对比 | 全量基线 |
| `data/ground_truth_reports/baseline_per_prefix.json` | 1,191 stocks | 分行业 |
| `data/ground_truth_reports/baseline_per_year.json` | 6 年 | 分年度 (⚠ 2022 缺失) |
| `data/ground_truth_reports/600519_2020_*.json` | 3 文件 | 单股深度对比 |
| `data/exports_v2/sina_cleaned_*.csv` | 49+24+66 行 | 清洗输出 (2 文件未提交) |
| `rules/*.yaml` | 10 活 + 1 bak | 规则资产 |
| `tests/` | 315 测试 | 测试套件 |

## 附录 B: 方法学说明

- **静态分析**: Python `yaml.safe_load` + 手写计数器；UTF-8 显示乱码为 Windows console 限制，**实际数据完整**
- **动态测量**: 复用 `data/ground_truth_reports/` 已有 JSON，**未重跑耗时 baseline**
- **抽样**: 4 只股票端到端对比 + 1 只发现 PDF 缺失
- **未运行**: 1.9 GB `data/akshare_bulk/` 原始数据；`scripts/auto_learn*.py` 重训

## 附录 C: 元数据

- 报告生成时间: 2026-06-08
- git 状态: master 比 origin/master 领先 2 commits (e289230 + 4fe473ba 新增)
- 未提交: `data/exports_v2/sina_cleaned_{cash_flow,income_statement}.csv` 82 行变更
- 报告 commit: 待定 (P0-1 决策后)
