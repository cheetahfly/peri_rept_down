# -*- coding: utf-8 -*-
"""
统一数据模型 - 所有数据源共享的财务数据结构
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import date


@dataclass
class FinancialItem:
    """单个财务科目"""
    item_code: Optional[str] = None        # RDS 代码如 F033N
    item_name: str = ""                     # 科目名称
    value: Optional[float] = None           # 数值（元）
    source: str = ""                        # 数据来源：rds/pdf/api
    confidence: float = 1.0                 # 置信度


@dataclass
class FinancialStatement:
    """单张财务报表"""
    stock_code: str = ""
    report_year: int = 0
    statement_type: str = ""                # balance_sheet / income_statement / cash_flow
    report_type: str = ""                   # annual / half / q1 / q3
    items: Dict[str, float] = field(default_factory=dict)
    item_codes: Dict[str, str] = field(default_factory=dict)  # name -> code
    unit: str = "元"
    source: str = ""
    confidence: float = 0.0


@dataclass
class StockFinancials:
    """一只股票的完整财务数据"""
    stock_code: str = ""
    stock_name: str = ""
    year: int = 0
    report_type: str = "annual"
    balance_sheet: Optional[FinancialStatement] = None
    income_statement: Optional[FinancialStatement] = None
    cash_flow: Optional[FinancialStatement] = None


# 报表类型常量
BALANCE_SHEET = "balance_sheet"
INCOME_STATEMENT = "income_statement"
CASH_FLOW = "cash_flow"

STATEMENT_TYPES = [BALANCE_SHEET, INCOME_STATEMENT, CASH_FLOW]

# 报告类型常量
ANNUAL = "annual"
HALF = "half"
Q1 = "q1"
Q3 = "q3"
