# -*- coding: utf-8 -*-
"""
提取模块配置
"""

import os

# 基础路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 提取结果存储目录
EXTRACTED_DIR = os.path.join(BASE_DIR, "data", "extracted")
EXTRACTED_BY_CODE_DIR = os.path.join(EXTRACTED_DIR, "by_code")

# SQLite数据库路径
EXTRACTION_DB_PATH = os.path.join(EXTRACTED_DIR, "extraction.db")

# 单位转换配置
UNIT_MULTIPLIERS = {
    "元": 1,
    "万元": 10000,
    "亿元": 100000000,
    "千元": 1000,
    "百万": 1000000,
    "万亿": 1000000000000,
}

# 报表类型
STATEMENT_TYPES = {
    "balance_sheet": "资产负债表",
    "income_statement": "利润表",
    "cash_flow": "现金流量表",
    "indicators": "财务指标",
}

# 报表关键词配置
SECTION_KEYWORDS = {
    "balance_sheet": ["资产负债表", "合并资产负债表", "银行资产负债表"],
    "income_statement": ["利润表", "损益表", "合并利润表"],
    "cash_flow": ["现金流量表", "合并现金流量表", "银行现金流量表"],
}

# SQL表结构
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS balance_sheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    report_year INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    item_value REAL,
    UNIQUE(stock_code, report_year, item_name)
);

CREATE TABLE IF NOT EXISTS income_statement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    report_year INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    item_value REAL,
    UNIQUE(stock_code, report_year, item_name)
);

CREATE TABLE IF NOT EXISTS cash_flow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    report_year INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    item_value REAL,
    UNIQUE(stock_code, report_year, item_name)
);

CREATE TABLE IF NOT EXISTS indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    report_year INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    item_value REAL,
    UNIQUE(stock_code, report_year, item_name)
);
"""

# 报表文件保存目录
REPORT_OUTPUT_DIR = os.path.join(BASE_DIR, "data", "reports")

# 导出目录
EXPORT_DIR = os.path.join(BASE_DIR, "data", "exports")

# 日志配置
LOG_FILE = os.path.join(BASE_DIR, "extraction.log")

# 标准科目别名映射 (标准名称 -> 可能出现的变体)
ITEM_ALIAS_MAP = {
    # 资产负债表
    "资产总计": ["资产总计", "资产合计", "资产总额", "资产总计数"],
    "负债合计": ["负债合计", "负债总计", "负债总额", "负债总计数"],
    "所有者权益合计": ["所有者权益合计", "股东权益合计", "所有者权益总计", "股东权益总计", "权益合计"],
    "归属母公司股东权益合计": ["归属母公司股东权益合计", "归属母公司权益合计", "归属于母公司股东权益合计"],
    "流动资产合计": ["流动资产合计", "流动资产总额"],
    "非流动资产合计": ["非流动资产合计", "非流动资产总额"],
    "流动负债合计": ["流动负债合计", "流动负债总额"],
    "非流动负债合计": ["非流动负债合计", "非流动负债总额"],
    "负债和所有者权益总计": ["负债和所有者权益总计", "负债及所有者权益总计", "负债及股东权益总计"],
    "货币资金": ["货币资金", "现金及现金等价物"],
    # 利润表
    "营业收入": ["营业收入", "营业总收入", "营业收入合计"],
    "营业成本": ["营业成本", "营业总成本"],
    "营业利润": ["营业利润"],
    "利润总额": ["利润总额"],
    "净利润": ["净利润", "净亏损"],
    "所得税费用": ["所得税费用", "所得税"],
    "归属于母公司所有者的净利润": ["归属于母公司所有者的净利润", "归属母公司股东净利润"],
    "销售费用": ["销售费用", "营业费用"],
    "管理费用": ["管理费用"],
    "研发费用": ["研发费用"],
    "财务费用": ["财务费用"],
    "公允价值变动收益": ["公允价值变动收益", "公允价值变动损益"],
    "投资收益": ["投资收益"],
    "资产减值损失": ["资产减值损失", "信用减值损失"],
    # 现金流量表
    "经营活动产生的现金流量净额": [
        "经营活动产生的现金流量净额", "经营活动现金流量净额",
        "经营活动产生现金流量净额",
    ],
    "投资活动产生的现金流量净额": [
        "投资活动产生的现金流量净额", "投资活动现金流量净额",
    ],
    "筹资活动产生的现金流量净额": [
        "筹资活动产生的现金流量净额", "筹资活动现金流量净额",
        "融资活动产生的现金流量净额",
    ],
    "现金及现金等价物净增加额": ["现金及现金等价物净增加额", "现金及现金等价物净减少额"],
    "期初现金及现金等价物余额": ["期初现金及现金等价物余额", "年初现金及现金等价物余额"],
    "期末现金及现金等价物余额": ["期末现金及现金等价物余额", "年末现金及现金等价物余额"],
}

# 各报表类型的预期科目数（单源真理）
# 恢复触发阈值 = EXPECTED_ITEMS // 3（非常少，触发深层恢复）
# 质量门控预期 = EXPECTED_ITEMS // 2（中等，评价置信度）
# 完整性分母   = EXPECTED_ITEMS     （100% = 完整提取）
EXPECTED_ITEMS_PER_TYPE = {
    "balance_sheet": 30,
    "income_statement": 20,
    "cash_flow": 30,
}

# 各报表类型的标准科目列表（按展示顺序）
STATEMENT_TYPE_STANDARD_ITEMS = {
    "balance_sheet": [
        "货币资金", "交易性金融资产", "应收票据", "应收账款", "存货",
        "流动资产合计", "长期股权投资", "固定资产", "无形资产",
        "非流动资产合计", "资产总计",
        "短期借款", "应付账款", "流动负债合计",
        "长期借款", "非流动负债合计", "负债合计",
        "所有者权益合计", "归属母公司股东权益合计",
        "负债和所有者权益总计",
    ],
    "income_statement": [
        "营业收入", "营业成本", "销售费用", "管理费用", "研发费用",
        "财务费用", "公允价值变动收益", "投资收益", "营业利润",
        "利润总额", "所得税费用", "净利润",
        "归属于母公司所有者的净利润",
    ],
    "cash_flow": [
        "经营活动产生的现金流量净额",
        "投资活动产生的现金流量净额",
        "筹资活动产生的现金流量净额",
        "现金及现金等价物净增加额",
        "期初现金及现金等价物余额",
        "期末现金及现金等价物余额",
    ],
    "indicators": [],
}
