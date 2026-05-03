# peri_rept_down

财报年报数据提取系统 - 从PDF年报中自动提取资产负债表、利润表、现金流量表数据

## 功能特性

### 核心功能
- **三大表提取**: 资产负债表、利润表、现金流量表
- **智能页面识别**: 自动识别财务报表所在页面，排除目录页、附注页干扰
- **乱码检测与恢复**: 检测CID字体乱码，自动切换到PDF2HTMLEX/LibreOffice备选解析
- **跨页表格合并**: 自动合并跨页表格
- **表格缓存**: 避免重复解析，提升性能

### 解析引擎
- **pdfplumber**: 主解析器，快速文本提取
- **PyMuPDF**: 备选解析器，乱码检测
- **HTML转换**: pdf2htmlEX/LibreOffice转换处理自定义字体PDF
- **OCR备选**: Tesseract/OCR.space处理极端乱码情况

### 测试覆盖
- **回归测试**: 5只核心股票 (000001, 600000, 600089, 600196, 603501)
- **扩展测试**: 9只股票，覆盖金融、制造、医药、半导体等行业
- **置信度评分**: 量化提取质量

## 安装依赖

```bash
pip install -r requirements.txt

# 可选: Tesseract OCR (用于极端乱码PDF)
# Windows: 下载安装包并添加到PATH
# Linux: sudo apt install tesseract-ocr
```

## 快速开始

### Python API

```python
from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor

# 提取单个PDF的三大表
pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"

with PdfParser(pdf_path) as parser:
    # 资产负债表
    bs_extractor = BalanceSheetExtractor(parser)
    bs_result = bs_extractor.extract()
    print(f"BS置信度: {bs_extractor.calculate_confidence(bs_result)['overall']:.2%}")
    print(f"提取项数: {len(bs_result.get('data', {}))}")

    # 利润表
    is_extractor = IncomeStatementExtractor(parser)
    is_result = is_extractor.extract()

    # 现金流量表
    cf_extractor = CashFlowExtractor(parser)
    cf_result = cf_extractor.extract()
```

### 命令行工具

```bash
# 提取单个PDF
python -m extraction.cli extract data/by_code/000001/000001_平安银行_2024_年报.pdf

# 批量处理
python -m extraction.cli batch data/by_code --years 2024

# 运行回归测试
pytest tests/test_regression.py -v

# 运行扩展测试
pytest tests/test_regression.py --extended -v
```

### 使用HybridParser (自动级联 fallback)

```python
from extraction.parsers.hybrid_parser import HybridParser

parser = HybridParser(pdf_path)
result = parser.extract_tables(page_num=0)
```

## 项目结构

```
extraction/
├── parsers/                 # PDF/HTML解析器
│   ├── pdf_parser.py        # pdfplumber封装
│   ├── pymupdf_parser.py   # PyMuPDF备选
│   ├── html_parser.py       # HTML表格解析
│   ├── html_converter.py    # PDF转HTML
│   ├── hybrid_parser.py     # 级联fallback解析器
│   └── ocr_parser.py        # OCR备选
├── extractors/              # 财务报表提取器
│   ├── base.py              # 基础提取器
│   ├── balance_sheet.py     # 资产负债表
│   ├── income_statement.py  # 利润表
│   └── cash_flow.py         # 现金流量表
├── storage/                 # 数据存储
│   └── sqlite_store.py      # SQLite存储
├── config.py                # 配置
└── cli.py                   # 命令行工具
tests/
├── test_regression.py       # 回归测试
├── regression_config.py     # 测试配置
└── test_expansion.py        # 扩展测试
```

## 提取质量

| 指标 | 数值 |
|------|------|
| 批量处理成功率 | 100% (39/39) |
| 高质量提取率 | ~97% (194/200 JSON) |
| 平均置信度 | 85%+ |

### 已知限制
- **CID字体PDF**: 部分PDF使用自定义字体编码，无法直接解析
- **跨页表格**: 复杂跨页格式可能需要人工检查
- **半年报**: 非年报文件支持有限

## License

MIT
