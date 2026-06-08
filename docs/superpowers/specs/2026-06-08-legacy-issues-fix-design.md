# 遗留问题修复设计

**创建日期**: 2026-06-08
**项目**: peri_rept_down (A股财务数据多源清洗流水线)
**范围**: 4 个遗留问题修复
**策略**: 按优先级串行 (P0 → P1)

## 1. 目标

解决以下 4 个遗留问题，提升流水线完整性和准确率：

| 优先级 | 问题 | 影响 |
|--------|------|------|
| **P0-2a** | 13 个 test_word_recovery 失败 — PDF 缺失 | 测试可信度 |
| **P0-4** | baseline_per_year.json 2022 数据全 0 | 基线准确性 |
| **P1-7** | 为银行单独输出 F057N | 银行 IS 数据 |
| **P1-1** | IS 88.89% 值准确率差距 | 整体准确率 |

## 2. 执行顺序

### 2.1 P0-2a: test_word_recovery PDF 缺失 (30 min)

**根因**: `data/by_code/600016/` PDF 文件缺失，测试直接引用不存在的文件。

**修复步骤**:
1. 检查 `data/by_code/600016/` 目录内容
2. 如果有批量下载脚本，重新下载 600016 PDF
3. 如果无法下载，在测试中添加 `@pytest.mark.skipif` 跳过数据缺失的测试
4. 运行 `pytest tests/test_word_recovery.py` 验证

**预期结果**: 13 个测试通过或跳过（不再 FAIL）

---

### 2.2 P0-4: 2022 年基线数据全 0 (1-2 h)

**根因**: `baseline_2019_2022.py` 的 scope 声明包含 2022，但实际数据未生成。

**修复步骤**:
1. 检查 Sina 原始数据中是否有 2022 年 12 月 31 日的数据
   ```bash
   python -c "import pandas as pd; df = pd.read_csv('data/akshare_bulk/000001_balance_sheet.csv'); print(df[df['报告日'].astype(str).str.startswith('2022')])"
   ```
2. 如果有 2022 数据，重新运行 baseline 生成
3. 如果没有，修正 scope 字符串移除 2022
4. 更新 `data/ground_truth_reports/baseline_per_year.json`

**预期结果**: baseline_per_year.json 2022 数据非零，或 scope 正确反映实际数据

---

### 2.3 P1-7: 为银行单独输出 F057N (2-3 h)

**根因**: `aliases.yaml` 将 `资产减值损失`、`信用减值损失`、`其他资产减值损失` 视为同一 canonical。

**修复步骤**:
1. 重构 `rules/aliases.yaml`：
   - 为银行单独定义 `信用减值损失` canonical
   - 在 `income_statement/annual` 中添加独立的 `信用减值损失` 条目
2. 在 `rules/value_mapping_rules.yaml` 中添加银行专项规则
3. 更新 `rules/field_order.yaml` 确保 F057N 有正确的 display_order
4. 重跑清洗流水线验证 F057N 出现在输出中
5. 运行 `pytest tests/ground_truth/test_rule_cleaner.py` 验证

**预期结果**: 银行 IS 中出现 F057N (信用减值损失) 字段

---

### 2.4 P1-1: IS 值准确率提升 (4-6 h)

**根因**: 银行 IS 数据结构与非银行完全不同，导致 compare_stock 匹配策略失效。

**具体问题**:
1. **别名冲突**: `其中：利息收入` 在 normalize_name 后变成 `利息收入`，与 `利息收入` 的别名冲突
2. **重复匹配**: `销售费用` 和 `管理费用` 都映射到 `业务及管理费`，导致同一 Sina 字段被匹配两次
3. **过于激进的匹配**: `cid_value` 和 `value_exact` 策略会根据值的大小匹配不相关的字段
4. **影响**: 000001 IS 值准确率仅 11.1%，而 600519 IS 值准确率 96.7%

**修复步骤**:
1. 重构 `compare_stock` 函数的匹配策略，增加银行专项的匹配规则
2. 为银行和非银行定义不同的 `alias_map`
3. 修复 `get_aliases` 中的别名克隆逻辑，避免重复匹配
4. 添加更严格的价值匹配阈值

**预期结果**: 银行 IS 值准确率从 11% 提升到 80%+，整体 IS 值准确率从 62% 提升到 90%+

## 3. 验证检查点

每个步骤完成后验证：

| 步骤 | 验证命令 | 预期结果 |
|------|----------|----------|
| P0-2a | `pytest tests/test_word_recovery.py` | 13 个测试通过或跳过 |
| P0-4 | `cat data/ground_truth_reports/baseline_per_year.json` | 2022 数据非零 |
| P1-7 | 检查清洗输出中 F057N | 银行 IS 包含 F057N |
| P1-1 | `cat data/ground_truth_reports/baseline_2019_2022.json` | IS 值准确率 >90% |

## 4. 约束

- **只读**: 不修改业务代码逻辑，仅调整规则和数据
- **串行执行**: 每个步骤完成后验证再进入下一步
- **测试优先**: 每个修复都要有对应的测试验证
