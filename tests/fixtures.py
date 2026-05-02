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
        "id": "000001_2024_bs",
        "stock_code": "000001",
        "company_name": "平安银行",
        "year": 2024,
        "report_type": "年报",
        "pdf_file": "000001_平安银行_2024_年报.pdf",
        "expected_confidence": {"BS": 1.0, "IS": 1.0, "CF": 1.0},
        "known_values": {
            "资产总计": 57692700000,
            "负债合计": 52744280000,
            "净利润": 445080000,
        },
    },
    {
        "id": "000001_2024_is",
        "stock_code": "000001",
        "company_name": "平安银行",
        "year": 2024,
        "report_type": "年报",
        "pdf_file": "000001_平安银行_2024_年报.pdf",
        "expected_confidence": {"IS": 1.0},
        "known_values": {
            "营业收入": 1466950000,
            "净利润": 445080000,
            "利润总额": 547380000,
        },
    },
    {
        "id": "000001_2024_cf",
        "stock_code": "000001",
        "company_name": "平安银行",
        "year": 2024,
        "report_type": "年报",
        "pdf_file": "000001_平安银行_2024_年报.pdf",
        "expected_confidence": {"CF": 1.0},
        "known_values": {
            "经营活动产生的现金流量净额": 633360000,
            "投资活动使用的现金流量净额": -318590000,
        },
    },
    {
        "id": "600000_2024_bs",
        "stock_code": "600000",
        "company_name": "浦发银行",
        "year": 2024,
        "report_type": "年报",
        "pdf_file": "600000_浦发银行_2024_年报.pdf",
        "expected_confidence": {"BS": 1.0, "IS": 1.0, "CF": 1.0},
        "known_values": {
            "资产总计": None,  # 待验证
            "负债合计": None,
            "净利润": 45835000,
        },
    },
    {
        "id": "600000_2024_is",
        "stock_code": "600000",
        "company_name": "浦发银行",
        "year": 2024,
        "report_type": "年报",
        "pdf_file": "600000_浦发银行_2024_年报.pdf",
        "expected_confidence": {"IS": 1.0},
        "known_values": {
            "营业收入": 170748000,
            "净利润": 45835000,
            "利润总额": 48366000,
        },
    },
    {
        "id": "600000_2024_cf",
        "stock_code": "600000",
        "company_name": "浦发银行",
        "year": 2024,
        "report_type": "年报",
        "pdf_file": "600000_浦发银行_2024_年报.pdf",
        "expected_confidence": {"CF": 1.0},
        "known_values": {
            "经营活动产生的现金流量净额": -333654000,
            "投资活动使用的现金流量净额": -83552000,
        },
    },
    {
        "id": "600000_2025_cf",
        "stock_code": "600000",
        "company_name": "浦发银行",
        "year": 2025,
        "report_type": "年报",
        "pdf_file": "600000_浦发银行_2025_年报.pdf",
        "expected_confidence": {"CF": 1.0},  # 已修复 - 2025格式使用简化关键字
        "known_values": {},
    },
]

# 扩展测试用例：添加2025年数据（当PDF可用时）
FUTURE_FIXTURES = [
    {
        "id": "000001_2025_bs",
        "stock_code": "000001",
        "company_name": "平安银行",
        "year": 2025,
        "report_type": "年报",
        "pdf_file": "000001_平安银行_2025_年报.pdf",
        "expected_confidence": {"BS": 1.0, "IS": 1.0, "CF": 1.0},
        "known_values": {},
    },
    {
        "id": "600000_2025_bs",
        "stock_code": "600000",
        "company_name": "浦发银行",
        "year": 2025,
        "report_type": "年报",
        "pdf_file": "600000_浦发银行_2025_年报.pdf",
        "expected_confidence": {"BS": 1.0, "IS": 1.0, "CF": 1.0},
        "known_values": {},
    },
]

# 扩展测试股票列表
# 这些是已验证可正常提取的股票
SUPPORTED_STOCKS = {
    "000001": {
        "name": "平安银行",
        "industry": "银行",
        "parser": "pdfplumber",
        "notes": "标准格式，提取率100%",
    },
    "600000": {
        "name": "浦发银行",
        "industry": "银行",
        "parser": "pdfplumber",
        "notes": "标准格式，提取率100%",
    },
}

# 需要特殊处理的股票（LibreOffice模式）
LIBREOFFICE_STOCKS = {
    "600036": {
        "name": "招商银行",
        "industry": "银行",
        "notes": "自定义字体编码，使用LibreOffice+表格重构",
    },
    "600111": {
        "name": "北方稀土",
        "industry": "有色金属",
        "notes": "自定义字体编码，使用LibreOffice+表格重构",
    },
}

# 不支持的PDF列表（需要OCR）
UNSUPPORTED_STOCKS = [
    {
        "stock_code": "600036",
        "company_name": "招商银行",
        "issue": "PDF使用自定义字体编码，文本提取工具无法正确解码",
        "workaround": "已使用LibreOffice方案解决",
        "status": "resolved",
    },
    {
        "stock_code": "600111",
        "company_name": "北方稀土",
        "issue": "PDF使用自定义字体编码，文本提取工具无法正确解码",
        "workaround": "已使用LibreOffice方案解决",
        "status": "resolved",
    },
]

# 待测试股票（需要下载更多年报）
PENDING_STOCKS = {
    "000002": {"name": "万科A", "industry": "房地产"},
    "600098": {"name": "广州发展", "industry": "公用事业"},
    "600550": {"name": "保变电气", "industry": "电气设备"},
    "000791": {"name": "甘肃能源", "industry": "能源"},
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
