# -*- coding: utf-8 -*-
"""
提取配置 - 从原 extraction/config.py 迁移
"""
import os

# 目录配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BY_CODE_DIR = os.path.join(BASE_DIR, "data", "extracted", "by_code")
EXPORTS_DIR = os.path.join(BASE_DIR, "data", "exports")
REPORTS_DIR = os.path.join(BASE_DIR, "data", "reports")
RULES_DIR = os.path.join(BASE_DIR, "rules")

# 单位乘数
UNIT_MULTIPLIERS = {
    "元": 1,
    "千元": 1000,
    "万元": 10000,
    "百万": 1000000,
    "亿元": 100000000,
    "万亿": 1000000000000,
}

# 各报表类型期望的项目数量（用于质量评分）
EXPECTED_ITEMS_PER_TYPE = {
    "balance_sheet": 45,
    "income_statement": 35,
    "cash_flow": 45,
}

# 章节关键词（从 rules/section_keywords.yaml 加载）
def _load_section_keywords() -> dict:
    import yaml
    path = os.path.join(RULES_DIR, "section_keywords.yaml")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError):
        return {}

SECTION_KEYWORDS = _load_section_keywords()

# 别名（从rules/aliases.yaml加载）
def get_aliases(statement_type: str, report_type: str = "annual") -> dict:
    """按 statement_type × report_type 加载别名"""
    import yaml
    path = os.path.join(RULES_DIR, "aliases.yaml")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError):
        return {}
    # 先尝试最精确的层级，逐级回退
    for level in [(statement_type, report_type), (statement_type, "default"), ("default",)]:
        d = data
        for key in level:
            d = d.get(key, {})
        if d:
            return d
    return {}

CATEGORY_NAME_TO_TYPE = {
    "年报": "annual", "半年报": "half",
    "一季报": "q1", "一季报": "q1",
    "三季报": "q3", "第三季度报告": "q3",
}
