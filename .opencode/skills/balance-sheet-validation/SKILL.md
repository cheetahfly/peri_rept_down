---
name: balance-sheet-validation
description: 验证资产负债表平衡 (资产总计 = 负债合计 + 股东权益合计)，确保提取数据正确性
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: validation
---

## What I do

验证资产负债表数据是否平衡，即 **资产总计 = 负债合计 + 股东权益合计**。

## When to use me

- 提取资产负债表后验证数据正确性
- 用户要求检查 "资产负债表平衡"
- 对比不同年份数据时
- 发现提取数据异常时排查

## Validation Logic

### 关键科目匹配

从提取的数据中查找以下科目：

| 模式键 | 匹配关键词 |
|--------|-----------|
| assets_total | 资产总计、资产合计、资产总额 |
| liabilities_total | 负债合计、负债总计、负债总额 |
| equity_total | 所有者权益合计、股东权益合计、权益合计 |

### 平衡公式

```
资产总计 = 负债合计 + 股东权益合计
```

### 容差范围

差异 > 资产总计 × 1% 时判定为不平衡

## How to validate

### 方式1: 使用 Extractor 内置验证

```python
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.parsers.pdf_parser import PdfParser

with PdfParser("path/to/pdf.pdf") as parser:
    extractor = BalanceSheetExtractor(parser)
    result = extractor.extract()
    is_valid, error_msg = extractor.validate(result)
    print(f"Valid: {is_valid}, Message: {error_msg}")
```

### 方式2: 手动验证（LibreOffice 模式）

```python
from extraction.parsers.hybrid_parser import HybridParser

with HybridParser("path/to/pdf.pdf", force_lo=True) as parser:
    bs_df = parser.extract_balance_sheet()
    # 查找资产总计、负债合计、权益合计行
    # 计算验证
```

### 方式3: 从 CSV 文件验证

```python
import pandas as pd

df = pd.read_csv("data/by_code/600036/bs_final.csv")
# 查找关键行并验证
```

## 验证结果解读

| 结果 | 含义 | 操作 |
|------|------|------|
| 平衡 | 资产 = 负债 + 权益，差异 < 1% | 提取成功 |
| 不平衡 | 差异 > 1% | 检查解析器或 PDF 格式 |
| 关键科目缺失 | 未找到资产总计等 | 可能需要人工检查 |

## 600036 招商银行验证示例

```
资产总计: 12,657,151 百万元 (2025/06)
负债合计: 11,415,746 百万元
股东权益合计: 1,241,405 百万元
负债 + 权益: 12,657,151 百万元 ✓ 平衡
```

## 常见不平衡原因

1. **PDF 表格格式异常** - 某些行被遗漏
2. **跨列数据未正确处理** - 附注列被误解析
3. **单位不一致** - 部分数据为百万，部分为元
4. **PDF 编码问题** - 乱码导致数值解析错误

## 阈值配置

当前容差阈值: **1%** (在 `balance_sheet.py` 的 `validate` 方法中)

如需调整，修改 `extraction/extractors/balance_sheet.py` 第93行：
```python
tolerance = abs(assets_total * 0.01)  # 0.01 = 1%
```
