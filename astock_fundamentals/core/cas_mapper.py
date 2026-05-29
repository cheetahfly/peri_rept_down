# extraction/cas_mapper.py
from typing import Dict, Optional

# CAS科目代码映射
CAS_MAPPING = {
    # 资产负债表
    "货币资金": {"code": "1001", "name": "货币资金"},
    "应收账款": {"code": "1122", "name": "应收账款"},
    "存货": {"code": "1405", "name": "存货"},
    "固定资产": {"code": "1601", "name": "固定资产"},
    "无形资产": {"code": "1701", "name": "无形资产"},
    "短期借款": {"code": "2001", "name": "短期借款"},
    "长期借款": {"code": "2501", "name": "长期借款"},
    "实收资本": {"code": "4001", "name": "实收资本"},
    "未分配利润": {"code": "4103", "name": "未分配利润"},
    "资产总计": {"code": "9999", "name": "资产总计"},
    "负债合计": {"code": "9998", "name": "负债合计"},
    "股东权益合计": {"code": "9997", "name": "股东权益合计"},
    # 利润表
    "营业收入": {"code": "6001", "name": "营业收入"},
    "营业成本": {"code": "6401", "name": "营业成本"},
    "销售费用": {"code": "6601", "name": "销售费用"},
    "管理费用": {"code": "6602", "name": "管理费用"},
    "财务费用": {"code": "6603", "name": "财务费用"},
    "净利润": {"code": "6801", "name": "净利润"},
    # 现金流量表
    "经营活动产生的现金流量净额": {"code": "E001", "name": "经营活动产生的现金流量净额"},
    "投资活动产生的现金流量净额": {"code": "E002", "name": "投资活动产生的现金流量净额"},
    "筹资活动产生的现金流量净额": {"code": "E003", "name": "筹资活动产生的现金流量净额"},
}

# 行业变体映射
INDUSTRY_VARIANTS = {
    "bank": {
        "存放中央银行款项": "1002",
        "拆出资金": "1003",
        "吸收存款": "2002",
    },
    "insurance": {
        "保费收入": "6002",
        "赔付支出": "6402",
        "准备金": "2801",
    }
}

# 公司变体到标准名称的映射
VARIANT_TO_STANDARD = {
    "货币及现金等价物": "货币资金",
    "现金及现金等价物": "货币资金",
    "应收账款净额": "应收账款",
    "固定资产原值": "固定资产",
}

class ChartOfAccountsMapper:
    """CAS（中国企业会计准则）科目映射器"""

    def __init__(self, industry: str = "general"):
        self.industry = industry
        self.variants = INDUSTRY_VARIANTS.get(industry, {})

    def map_item(self, original_name: str, statement_type: str) -> Dict:
        """将原始科目名映射到CAS标准"""
        # 先检查行业变体
        if self.industry != "general" and original_name in self.variants:
            code = self.variants[original_name]
            return {
                "original_name": original_name,
                "cas_name": original_name,
                "cas_code": code,
                "mapped": True,
            }

        # 先检查变体
        standard = VARIANT_TO_STANDARD.get(original_name)
        if not standard:
            standard = original_name

        # 查找CAS映射
        cas_info = CAS_MAPPING.get(standard, {})
        if not cas_info:
            # 模糊匹配
            for std_name, info in CAS_MAPPING.items():
                if original_name in std_name or std_name in original_name:
                    cas_info = info
                    standard = std_name
                    break

        return {
            "original_name": original_name,
            "cas_name": cas_info.get("name", standard),
            "cas_code": cas_info.get("code"),
            "mapped": bool(cas_info),
        }

    def map_statement(self, data: Dict, statement_type: str) -> Dict:
        """映射整个报表"""
        mapped = {}
        for item_name, item_data in data.items():
            if isinstance(item_data, dict):
                value = item_data.get("value", item_data.get("数值", 0))
            else:
                value = item_data
            mapped[item_name] = self.map_item(item_name, statement_type)
            mapped[item_name]["value"] = value
        return mapped
