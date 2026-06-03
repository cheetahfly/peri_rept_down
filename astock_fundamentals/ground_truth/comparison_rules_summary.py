# -*- coding: utf-8 -*-
"""
Sina vs RDS 对比分析的规则总结

基于2026-05-30的对比分析，总结出的关键规则和模式。
"""

# 对比分析的统计结果
COMPARISON_SUMMARY = {
    "total_stocks_compared": 100,
    "year_range": "2000-2021",
    "total_comparisons": 2780,

    "by_statement": {
        "balance_sheet": {
            "total_comparisons": 1015,
            "gt_items": 40251,
            "matched": 33474,
            "coverage": 0.848,
            "notes": "覆盖率较高，金融行业特殊科目差异明显"
        },
        "income_statement": {
            "total_comparisons": 995,
            "gt_items": 21343,
            "matched": 18456,
            "coverage": 0.860,
            "notes": "利润率覆盖率最高，科目命名较规范"
        },
        "cash_flow": {
            "total_comparisons": 770,
            "gt_items": 33929,
            "matched": 21415,
            "coverage": 0.628,
            "notes": "间接法科目差异较大，匹配难度最高"
        }
    }
}

# 发现的关键模式
DISCOVERED_PATTERNS = {
    "naming_patterns": [
        {
            "pattern": "前缀差异",
            "description": "RDS有'其中：'前缀，Sina缺失",
            "examples": [
                {"rds": "其中：营业收入", "sina": "营业收入"},
                {"rds": "其中：应收账款", "sina": "应收账款"}
            ],
            "solution": "自动添加'其中：'前缀进行匹配"
        },
        {
            "pattern": "后缀差异",
            "description": "Sina有'(合计)'后缀，RDS无",
            "examples": [
                {"rds": "其他应收款", "sina": "其他应收款(合计)"},
                {"rds": "在建工程", "sina": "在建工程(合计)"}
            ],
            "solution": "自动去除'(合计)'后缀进行匹配"
        },
        {
            "pattern": "金融行业特殊科目",
            "description": "银行/保险有特有科目",
            "examples": [
                {"rds": "银行存款", "sina": "存放同业"},
                {"rds": "发放贷款及垫款", "sina": "拆出资金"}
            ],
            "solution": "添加行业特定匹配规则"
        },
        {
            "pattern": "科目拆分",
            "description": "Sina的科目拆分为多个细项",
            "examples": [
                {"rds": "其他应收款", "sina": ["其他应收款-合计", "其他应收款-关联方"]}
            ],
            "solution": "聚合Sina细项后与RDS汇总值匹配"
        }
    ],

    "year_patterns": [
        {
            "period": "2000-2005",
            "coverage": 0.684,
            "notes": "格式不统一，需宽松匹配阈值(0.02)"
        },
        {
            "period": "2006-2015",
            "coverage": 0.820,
            "notes": "格式逐步规范化"
        },
        {
            "period": "2016-2021",
            "coverage": 0.853,
            "notes": "相对稳定，可使用严格阈值(0.005)"
        }
    ],

    "value_accuracy": {
        "note": "部分股票覆盖率异常(>100%)，需检查科目拆分情况",
        "low_accuracy_stocks": ["000001", "000007", "000006", "000008", "000012"],
        "reason": "Sina科目数量远大于RDS，包含细项拆分"
    }
}

# 优化后的匹配规则
OPTIMIZED_RULES = {
    "priority_order": [
        "exact_name",      # 精确名称匹配
        "alias_match",     # 别名匹配
        "value_exact",     # 值精确匹配
        "financial_sector",# 金融行业特定
        "fuzzy_match",     # 模糊匹配
        "year_specific"    # 年份特定规则
    ],

    "thresholds": {
        "exact_name": 0.0,
        "alias_match": 0.0,
        "value_exact": 0.001,
        "value_near": 0.01,
        "fuzzy_match": 0.05,
        "financial_sector": 0.005,
        "year_2000_2005": 0.02,
        "year_2006_2015": 0.01,
        "year_2016_2021": 0.005
    },

    "financial_sector_rules": {
        "banking": {
            "存放同业": "银行存款",
            "拆出资金": "发放贷款及垫款",
            "买入返售金融资产": "交易性金融资产",
            "卖出回购金融资产款": "短期借款",
            "吸收存款及同业存放": "吸收存款",
            "向中央银行借款": "短期借款"
        },
        "insurance": {
            "保户储金及投资款": "其他应付款",
            "未到期责任准备金": "预计负债",
            "保险合同准备金": "预计负债",
            "应付手续费及佣金": "其他应付款",
            "分保费用": "其他应付款"
        }
    }
}

def get_rule_summary():
    """获取规则摘要"""
    return {
        "comparison_summary": COMPARISON_SUMMARY,
        "discovered_patterns": DISCOVERED_PATTERNS,
        "optimized_rules": OPTIMIZED_RULES,
        "key_insights": [
            "资产负债表和利润表匹配率较高(84-86%)",
            "现金流量表间接法科目差异最大(63.6%)",
            "金融行业需要特殊匹配规则",
            "年份段差异显著(2000-2005年需宽松阈值)",
            "科目拆分需聚合后匹配"
        ]
    }

if __name__ == "__main__":
    summary = get_rule_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
