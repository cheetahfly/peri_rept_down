---
name: ocr-debug
description: 诊断和调试 PDF 编码问题，决定使用哪种解析方案，处理需要 OCR 的股票
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: debugging
---

## What I do

诊断 PDF 编码问题，判断是否需要 OCR，并推荐合适的解析方案。

## When to use me

- PDF 出现乱码（如 600111 北方稀土）
- 用户要求 "检查 PDF 问题" 或 "调试 OCR"
- LibreOffice 转换后中文仍为乱码
- 新股票提取失败时

## PDF 编码问题判断流程

```
1. 使用 pdfplumber 提取样本文本
2. 检查是否乱码 → is_garbled_text()
   ├─ 正常文本 → 使用 PdfParser (pdfplumber)
   └─ 乱码 → 继续下一步
3. 尝试 LibreOffice 转换
   ├─ 转换成功 + 中文可读 → 使用 HybridParser (force_lo=True)
   └─ 仍乱码 → 需要 OCR 方案
```

## 乱码检测函数

位置: `extraction/parsers/html_converter.py`

```python
from extraction.parsers.html_converter import is_garbled_text

text = pdf_parser.extract_text(0)
if is_garbled_text(text):
    print("检测到乱码")
```

## 已知问题股票

| 股票代码 | 公司名称 | 问题 | 当前状态 |
|----------|----------|------|----------|
| 600036 | 招商银行 | 自定义字体编码 | ✅ 已解决 (LibreOffice) |
| 600111 | 北方稀土 | 自定义字体编码，LO转换后仍乱码 | ❌ 需要OCR |

## OCR 方案选项

### 方案1: Tesseract OCR (推荐)

```bash
# 安装
winget install tesseract

# 或使用 pytesseract
pip install pytesseract
```

优点: 开源免费，跨平台
缺点: 对中文识别需要训练数据

### 方案2: PaddleOCR

```bash
pip install paddlepaddle paddleocr
```

优点: 中文识别效果好
缺点: 依赖较多，安装复杂

### 方案3: EasyOCR

```bash
pip install easyocr
```

优点: 使用简单
缺点: 置信度低，位置信息不准确

## LibreOffice 转换调试

```python
from extraction.parsers.html_converter import convert_pdf_to_html
from extraction.parsers.lo_table_parser import LibreOfficeTableParser

# 转换 PDF
success, html_path = convert_pdf_to_html(pdf_path, temp_dir)
if success:
    # 尝试解析
    parser = LibreOfficeTableParser(html_path)
    bs_df = parser.extract_balance_sheet()
    print(f"提取行数: {len(bs_df)}")
else:
    print(f"转换失败: {html_path}")
```

## 不支持 PDF 记录

当确定 PDF 无法提取时，更新 `UNSUPPORTED_PDFS.py`:

```python
UNSUPPORTED_PDFS = [
    # ...
    {
        "stock_code": "600111",
        "company_name": "北方稀土",
        "reason": "自定义字体编码，LibreOffice转换后仍乱码",
        "recommended_solution": "需要OCR方案（Tesseract/PaddleOCR）",
        "date_added": "2026-03-31"
    }
]
```

## 决策树

```
PDF 提取失败?
├─ 检查 PDF 是否存在
├─ 检查文件是否损坏
└─ 检查编码问题
   ├─ is_garbled_text() == False → 正常，使用 PdfParser
   ├─ is_garbled_text() == True + LO成功 → 使用 HybridParser(force_lo=True)
   └─ is_garbled_text() == True + LO失败 → OCR 方案或记录为不支持
```

## 调试命令

```bash
# 检查 PDF 文本提取
python -c "
from extraction.parsers.pdf_parser import PdfParser
with PdfParser('data/by_code/600111/600111_北方稀土_2025_年报.pdf') as p:
    print(p.extract_text(0)[:500])
"

# 检查 LibreOffice 转换
python -c "
from extraction.parsers.html_converter import convert_pdf_to_html
convert_pdf_to_html('path/to/pdf.pdf', 'temp_dir')
"
```
