---
name: financial-extraction-workflow
description: 财务报告完整提取工作流：下载PDF → 检测编码 → 选择解析器 → 提取三表 → 验证平衡 → 保存结果
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: extraction
---

## What I do

提供 A股财务报告 PDF 提取的完整标准化工作流，从下载到验证一站式完成。

## When to use me

- 提取新股票年报时
- 用户要求 "提取股票" 或 "下载年报"
- 需要完整流程指引时

## Complete Workflow

### Step 1: 下载 PDF

```bash
# 单只股票
python main.py --mode single --test-stock 000001

# 批量下载（在 main.py 中配置 stock_list）
python main.py --mode batch
```

PDF 保存位置: `data/by_code/<stock_code>/`

### Step 2: 检测编码并选择解析器

```python
from extraction.parsers.pdf_parser import PdfParser
from extraction.parsers.html_converter import is_garbled_text

pdf_path = "data/by_code/600036/600036_招商银行_2025_年报.pdf"

with PdfParser(pdf_path) as parser:
    sample_text = parser.extract_text(0) + parser.extract_text(1)
    
if is_garbled_text(sample_text):
    # 使用 HybridParser (LibreOffice 模式)
    from extraction.parsers.hybrid_parser import HybridParser
    parser = HybridParser(pdf_path, force_lo=True)
else:
    # 使用标准 PdfParser
    parser = PdfParser(pdf_path)
```

### Step 3: 提取财务报表

```python
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor

with PdfParser(pdf_path) as parser:
    # 资产负债表
    bs_ext = BalanceSheetExtractor(parser)
    bs_result = bs_ext.extract()
    bs_conf = bs_ext.calculate_confidence(bs_result)
    
    # 利润表
    is_ext = IncomeStatementExtractor(parser)
    is_result = is_ext.extract()
    is_conf = is_ext.calculate_confidence(is_result)
    
    # 现金流量表
    cf_ext = CashFlowExtractor(parser)
    cf_result = cf_ext.extract()
    cf_conf = cf_ext.calculate_confidence(cf_result)

print(f"BS: {bs_conf['overall']*100:.1f}%, IS: {is_conf['overall']*100:.1f}%, CF: {cf_conf['overall']*100:.1f}%")
```

### Step 4: LibreOffice 模式提取

```python
from extraction.parsers.hybrid_parser import HybridParser

with HybridParser(pdf_path, force_lo=True) as parser:
    bs_df = parser.extract_balance_sheet()
    is_df = parser.extract_income_statement()
    cf_df = parser.extract_cash_flow()
```

### Step 5: 验证资产负债表平衡

```python
from extraction.extractors.balance_sheet import BalanceSheetExtractor

with PdfParser(pdf_path) as parser:
    ext = BalanceSheetExtractor(parser)
    result = ext.extract()
    is_valid, msg = ext.validate(result)
    
if is_valid:
    print("资产负债表平衡 ✓")
else:
    print(f"资产负债表不平衡: {msg}")
```

### Step 6: 保存结果

```python
import os
import pandas as pd

output_dir = f"data/by_code/{stock_code}"
os.makedirs(output_dir, exist_ok=True)

# 保存 CSV
bs_df.to_csv(f"{output_dir}/bs_final.csv", index=False)
is_df.to_csv(f"{output_dir}/is_final.csv", index=False)
cf_df.to_csv(f"{output_dir}/cf_final.csv", index=False)
```

## 解析器选择指南

| PDF 状态 | 解析器 | 使用方法 |
|----------|--------|----------|
| 正常文本 | PdfParser | `PdfParser(pdf_path)` |
| 乱码 (pdf2htmlEX可用) | HtmlParser | `HybridParser(pdf_path, force_html=True)` |
| 乱码 (LibreOffice可用) | LibreOfficeTableParser | `HybridParser(pdf_path, force_lo=True)` |
| 乱码 (都无法解决) | OCR | 记录到 UNSUPPORTED_PDFS.py |

## 支持的股票

| 股票代码 | 公司名称 | 解析方式 |
|----------|----------|----------|
| 000001 | 平安银行 | pdfplumber |
| 600000 | 浦发银行 | pdfplumber |
| 600036 | 招商银行 | LibreOffice |
| 600111 | 北方稀土 | 需要OCR (暂不支持) |

## 输出文件格式

### 资产负债表 (bs_final.csv)

| 列名 | 说明 |
|------|------|
| 项目 | 科目名称 |
| 附注 | 附注编号（如 49(f)） |
| 2025年 | 2025年数据 |
| 2024年 | 2024年数据 |

### 利润表 (is_final.csv)

| 列名 | 说明 |
|------|------|
| 项目 | 科目名称 |
| 附注 | 附注编号 |
| 2025年 | 2025年数据 |
| 2024年 | 2024年数据 |

### 现金流量表 (cf_final.csv)

| 列名 | 说明 |
|------|------|
| 项目 | 科目名称 |
| 附注 | 附注编号 |
| 2025年 | 2025年数据 |
| 2024年 | 2024年数据 |

## 快速命令汇总

```bash
# 下载并提取单只股票
python main.py --mode single --test-stock 000001

# 运行测试验证
python tests/quick_verify.py

# 完整测试报告
python tests/test_runner.py --report

# 验证资产负债表平衡
# (见 balance-sheet-validation skill)
```
