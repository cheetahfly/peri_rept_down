# -*- coding: utf-8 -*-
"""
测试数据集定义

每个测试用例包含:
- stock_code: 股票代码
- company_name: 公司名称
- year: 报告年份
- report_type: 报告类型 (年报/半年报/季报)
- pdf_file: PDF文件名
- expected_confidence: 期望置信度
- known_values: 已知的关键数值（用于验证提取准确性）
"""

TEST_FIXTURES = [
    {
        "id": "000001_2025_bs",
        "stock_code": "000001",
        "company_name": "平安银行",
        "year": 2025,
        "report_type": "年报",
        "pdf_file": "000001_平安银行_平安银行：2025年年度报告.PDF",
        "expected_confidence": {"BS": 1.0, "IS": 1.0, "CF": 0.7},
        "known_values": {
            "资产总计": 5925777,
            "负债合计": 5374593,
            "营业收入": 131442,
            "净利润": 42633,
        },
    },
    {
        "id": "601318_2025_bs",
        "stock_code": "601318",
        "company_name": "中国平安",
        "year": 2025,
        "report_type": "年报",
        "pdf_file": "601318_中国平安_中国平安：中国平安2025年年度报告.PDF",
        "expected_confidence": {"BS": 1.0, "IS": 1.0, "CF": 0.7},
        "known_values": {
            "资产总计": 13898471,
            "负债合计": 12482483,
            "营业收入": 1050506,
            "净利润": 134778,
        },
    },
    {
        "id": "600887_2025_bs",
        "stock_code": "600887",
        "company_name": "伊利股份",
        "year": 2025,
        "report_type": "年报",
        "pdf_file": "600887_伊利股份_伊利股份：内蒙古伊利实业集团股份有限公司2025年年度报告.PDF",
        "expected_confidence": {"BS": 0.9, "IS": 0.8, "CF": 0.65},
        "known_values": {
            "资产总计": 152098516632,
            "营业收入": 115636231250,
            "净利润": 11513910754,
        },
    },
    {
        "id": "600036_2025_bs",
        "stock_code": "600036",
        "company_name": "招商银行",
        "year": 2025,
        "report_type": "年报",
        "pdf_file": "600036_招商银行_招商银行：招商银行股份有限公司2025年度报告.PDF",
        "expected_confidence": {"BS": 0.9, "IS": 1.0, "CF": 0.7},
        "known_values": {
            "资产总计": 13070523,
            "负债合计": 11789624,
            "营业收入": 337532,
            "净利润": 151126,
        },
    },
]

# 扩展测试用例：PDF存在但提取质量待验证
FUTURE_FIXTURES = [
    {
        "id": "000002_2025_bs",
        "stock_code": "000002",
        "company_name": "万科A",
        "year": 2025,
        "report_type": "年报",
        "pdf_file": "000002_万科A_万科A：2025年年度报告.PDF",
        "expected_confidence": {"BS": 0.8, "IS": 0.7, "CF": 0.6},
        "known_values": {},
    },
    {
        "id": "002475_2025_bs",
        "stock_code": "002475",
        "company_name": "立讯精密",
        "year": 2025,
        "report_type": "年报",
        "pdf_file": "002475_立讯精密_2025_年度报告.PDF",
        "expected_confidence": {"BS": 0.8, "IS": 0.7, "CF": 0.5},
        "known_values": {},
    },
]

# 已验证可正常提取的股票
SUPPORTED_STOCKS = {
    "000001": {
        "name": "平安银行",
        "industry": "银行",
        "parser": "pdfplumber",
        "notes": "标准格式，提取率100%",
    },
    "601318": {
        "name": "中国平安",
        "industry": "保险",
        "parser": "pdfplumber",
        "notes": "CID字体，但提取率良好",
    },
    "600887": {
        "name": "伊利股份",
        "industry": "食品饮料",
        "parser": "pdfplumber",
        "notes": "CID字体，文本解析回退",
    },
    "600036": {
        "name": "招商银行",
        "industry": "银行",
        "parser": "pdfplumber",
        "notes": "标准银行格式",
    },
    "002475": {
        "name": "立讯精密",
        "industry": "电子制造",
        "parser": "pdfplumber",
        "notes": "CID字体，提取率良好",
    },
}

# 需要特殊处理的PDF
LIBREOFFICE_STOCKS = {}

# 不支持的PDF列表
UNSUPPORTED_STOCKS = []

# 待测试股票（需要验证）
PENDING_STOCKS = {
    "000858": {"name": "五粮液", "industry": "白酒", "note": "半年报"},
    "600031": {"name": "三一重工", "industry": "工程机械"},
    "600585": {"name": "海螺水泥", "industry": "建材"},
    "600519": {"name": "贵州茅台", "industry": "白酒", "note": "CID字体严重"},
}


def get_all_fixtures():
    """获取所有可用的测试用例"""
    return TEST_FIXTURES


def get_fixture_by_id(fixture_id):
    """根据ID获取测试用例"""
    for fixture in TEST_FIXTURES + FUTURE_FIXTURES:
        if fixture["id"] == fixture_id:
            return fixture
    return None


def get_fixtures_by_stock(stock_code):
    """获取指定股票的所有测试用例"""
    return [f for f in TEST_FIXTURES if f["stock_code"] == stock_code]
