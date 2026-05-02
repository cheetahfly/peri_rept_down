---
name: pdf-testing
description: 运行测试验证 PDF 提取结果，适用于代码修改后验证和CI/CD
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: testing
---

## What I do

运行测试验证 PDF 财务报告提取结果，包括快速验证和完整测试。

## When to use me

- 修改解析器代码后验证功能
- 提取新股票后检查结果
- CI/CD 流程中验证提取准确性
- 用户要求 "运行测试" 或 "验证结果"

## How to use

### 快速验证（推荐日常使用）

```bash
python tests/quick_verify.py
```

### 完整测试（生成详细报告）

```bash
python tests/test_runner.py --report
```

### 单股票测试

```bash
python tests/test_runner.py --stock 600036 --report
```

### 指定测试用例

```bash
python tests/test_runner.py --fixture 600036_2025 --report
```

## 验证通过标准

- `overall` 置信度 >= 100% = PASS
- `overall` 置信度 >= 80% = 可接受
- `overall` 置信度 < 80% = FAIL

## 测试覆盖的报表

| 报表类型 | Extractor | 说明 |
|----------|-----------|------|
| 资产负债表 | BalanceSheetExtractor | BS |
| 利润表 | IncomeStatementExtractor | IS |
| 现金流量表 | CashFlowExtractor | CF |

## 测试结果位置

- 快速验证: `tests/results/quick_verify_<timestamp>.json`
- 完整报告: `tests/results/test_report_<timestamp>.json`

## 已知测试状态

| 股票 | 2024 BS | 2024 IS | 2024 CF | 2025 BS | 2025 IS | 2025 CF |
|------|---------|---------|---------|---------|---------|---------|
| 000001 平安银行 | 100% | 100% | 100% | 100% | 100% | 100% |
| 600000 浦发银行 | 100% | 100% | 100% | 100% | 100% | 100% |
| 600036 招商银行 | - | - | - | 100% | 100% | 100% |

## 故障排除

若测试失败：
1. 检查 PDF 文件是否存在于 `data/by_code/<stock_code>/`
2. 查看详细错误信息（运行测试时终端输出）
3. 检查是否为新股票需要 OCR 支持（如 600111）
