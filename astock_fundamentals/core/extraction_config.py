# -*- coding: utf-8 -*-
"""
提取模块配置 (moved to astock_fundamentals.core)
"""

import os
import yaml
from typing import Dict, List, Any

# 基础路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 规则文件目录
RULES_DIR = os.path.join(BASE_DIR, "rules")


def load_yaml_rule(filename: str, default: Any = None) -> Any:
    """从 rules/ 目录加载 YAML 规则文件，失败时返回默认值"""
    path = os.path.join(RULES_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError):
        return default

# 提取结果存储目录
EXTRACTED_DIR = os.path.join(BASE_DIR, "data", "extracted")
EXTRACTED_BY_CODE_DIR = os.path.join(EXTRACTED_DIR, "by_code")

# SQLite数据库路径
EXTRACTION_DB_PATH = os.path.join(EXTRACTED_DIR, "extraction.db")

# 单位转换配置（从 YAML 加载）
UNIT_MULTIPLIERS = load_yaml_rule("unit_detection.yaml", {}).get("unit_multipliers", {
    "元": 1,
    "万元": 10000,
    "亿元": 100000000,
    "千元": 1000,
    "百万": 1000000,
    "万亿": 1000000000000,
})

# 报表类型
STATEMENT_TYPES = {
    "balance_sheet": "资产负债表",
    "income_statement": "利润表",
    "cash_flow": "现金流量表",
    "indicators": "财务指标",
}

# 报表关键词配置（从 YAML 加载）
SECTION_KEYWORDS = load_yaml_rule("section_keywords.yaml", {
    "balance_sheet": ["资产负债表", "合并资产负债表", "银行资产负债表"],
    "income_statement": ["利润表", "损益表", "合并利润表"],
    "cash_flow": ["现金流量表", "合并现金流量表", "银行现金流量表"],
})

# 报表文件保存目录
REPORT_OUTPUT_DIR = os.path.join(BASE_DIR, "data", "reports")

# 导出目录
EXPORT_DIR = os.path.join(BASE_DIR, "data", "exports")

# 日志配置
LOG_FILE = os.path.join(BASE_DIR, "extraction.log")

# =============================================================================
# 科目别名映射 (分层结构: statement_type → report_type → 标准名 → 变体列表)
# =============================================================================
_ITEM_ALIAS_MAP_HIERARCHICAL = load_yaml_rule("aliases.yaml", {})


def _merge_sina_aliases(annual_block: Dict[str, List[str]], sina_block: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Merge sina_aliases_2019_2022 entries into the annual report-type block.

    For each (canonical_name, [sina_aliases]) in sina_block:
      - If canonical is in annual_block: append sina aliases to existing list
        (deduped, order-preserving).
      - If canonical is NEW (not in annual_block): create entry with
        canonical_name first, then sina aliases (deduped).
    Returns a fresh dict; does not mutate inputs.
    """
    if not sina_block:
        return annual_block
    merged: Dict[str, List[str]] = {}
    for k, v in annual_block.items():
        merged[k] = list(v or [])
    for canonical, sina_als in sina_block.items():
        existing = merged.setdefault(canonical, [])
        # Ensure canonical name is in its own alias list (so comparators
        # can match self-entries via reverse lookup)
        if canonical not in existing:
            existing.append(canonical)
        for a in sina_als or []:
            if a != canonical and a not in existing:
                existing.append(a)
    return merged


def _normalize_alias_key(name: str) -> str:
    """Normalize an alias key the same way comparator.normalize_name does.
    This ensures that alias-map lookups using normalized gt_names find the
    right entries even when normalize_name strips prefixes."""
    import re
    name = re.sub(r'_c\d+$', '', name)
    name = re.sub(r'^(其中[：:]|减[：:]|加[：:])', '', name)
    name = re.sub(r'^[一二三四五六七八九十]+[、.]', '', name)
    name = re.sub(r'^[（(][一二三四五六七八九十1234567890]+[)）]', '', name)
    name = re.sub(r'^\d+[、.]', '', name)
    name = re.sub(r'[（(][^)）]*$', '', name)
    return name.strip()


def get_aliases(statement_type: str, report_type: str = "annual") -> Dict[str, List[str]]:
    """
    Get alias map for a specific statement type and report type.

    Falls back to 'annual' if the specified report_type not found.
    Auto-merges sina_aliases_2019_2022 entries (populated by
    scripts/learn_sina_aliases.py) into the annual block.
    Also clones entries under normalized keys (e.g. '营业成本' <- '其中：营业成本')
    so that comparator.normalize_name's prefix-stripping doesn't miss matches.

    Args:
        statement_type: One of 'balance_sheet', 'income_statement', 'cash_flow'
        report_type: One of 'annual', 'half_year', 'quarter_q1', 'quarter_q3'

    Returns:
        Dict mapping standard item names to lists of variant names
    """
    if not _ITEM_ALIAS_MAP_HIERARCHICAL:
        return {}
    st_data = _ITEM_ALIAS_MAP_HIERARCHICAL.get(statement_type, {})
    annual_block = st_data.get("annual", {})
    sina_block = _ITEM_ALIAS_MAP_HIERARCHICAL.get("sina_aliases_2019_2022", {}).get(statement_type, {})
    annual_with_sina = _merge_sina_aliases(annual_block, sina_block)

    # Clone entries under their normalize_name-stripped keys so that
    # comparator's prefix-stripping (其中：/减：/加：) doesn't miss matches.
    # e.g. 其中：营业成本 -> dup to 营业成本
    # BUT: skip cloning if the stripped key already exists as a different
    # canonical (e.g. 利息收入 already exists, don't merge 其中：利息收入 into it).
    existing_canonicals = set(annual_with_sina.keys())
    extras: Dict[str, List[str]] = {}
    for canonical, aliases in list(annual_with_sina.items()):
        stripped = _normalize_alias_key(canonical)
        if stripped and stripped != canonical and stripped not in existing_canonicals:
            existing = extras.setdefault(stripped, [])
            for a in aliases or []:
                if a not in existing:
                    existing.append(a)

    if extras:
        annual_with_sina = dict(annual_with_sina)
        for stripped, aliases in extras.items():
            annual_with_sina.setdefault(stripped, [])
            for a in aliases:
                if a not in annual_with_sina[stripped]:
                    annual_with_sina[stripped].append(a)

    if report_type == "annual":
        return annual_with_sina
    # Other report types: fall back to their own block, else annual
    return st_data.get(report_type, annual_with_sina)


# Backward compatible - default to income_statement.annual
# This maintains compatibility with existing code that uses ITEM_ALIAS_MAP directly
ITEM_ALIAS_MAP = get_aliases("income_statement", "annual")

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
