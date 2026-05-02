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
