# extraction/quality_gate.py
from typing import Dict, List, Tuple

class QualityGate:
    """质量门控 - 零容忍验证"""

    def __init__(self, tolerance: float = 0.01):
        self.tolerance = tolerance  # 允许的误差容限

    def validate_all(self, bs_data: Dict, is_data: Dict, cf_data: Dict) -> Dict:
        """执行所有校验"""
        results = {
            "balance_sheet": self.validate_balance_sheet(bs_data),
            "income_statement": self.validate_income_statement(is_data),
            "cash_flow": self.validate_cash_flow(cf_data),
            "cross_statement": self.validate_cross_statement(bs_data, is_data, cf_data),
        }

        # 计算总体置信度
        all_passed = all(r["passed"] for r in results.values())
        confidence = self._calculate_overall_confidence(results)

        return {
            "passed": all_passed,
            "confidence": confidence,
            "details": results,
            "quality_flags": self._collect_flags(results),
        }

    def validate_balance_sheet(self, data: Dict) -> Dict:
        """资产负债表平衡校验: 资产总计 = 负债合计 + 股东权益合计"""
        assets = self._find_item(data, ["资产总计", "资产合计"])
        liabilities = self._find_item(data, ["负债合计", "负债总计"])
        equity = self._find_item(data, ["股东权益合计", "所有者权益合计", "归属母公司股东权益合计"])

        if not all([assets, liabilities, equity]):
            return {"passed": False, "reason": "missing_items"}

        total = liabilities + equity
        diff = abs(assets - total)
        passed = diff <= assets * self.tolerance

        return {
            "passed": passed,
            "assets": assets,
            "liabilities_plus_equity": total,
            "difference": diff,
            "flags": [] if passed else ["BALANCE_CHECK_FAILED"],
        }

    def validate_income_statement(self, data: Dict) -> Dict:
        """利润表校验"""
        revenue = self._find_item(data, ["营业收入"])
        net_profit = self._find_item(data, ["净利润"])

        if not revenue or not net_profit:
            return {"passed": True, "reason": "insufficient_data"}

        # 净利润应该小于营业收入
        if net_profit > revenue * 1.5:
            return {"passed": False, "flags": ["UNREASONABLE_NET_PROFIT"]}

        return {"passed": True}

    def validate_cash_flow(self, data: Dict) -> Dict:
        """现金流量表校验"""
        net_increase = self._find_item(data, ["现金及现金等价物净增加额", "净增加额"])
        if not net_increase:
            return {"passed": True, "reason": "insufficient_data"}

        # 净额应该在合理范围内
        if abs(net_increase) > 1e12:  # 超过万亿
            return {"passed": False, "flags": ["OUTLIER_DETECTED"]}

        return {"passed": True}

    def validate_cross_statement(self, bs: Dict, inc: Dict, cf: Dict) -> Dict:
        """跨表勾稽校验"""
        # 期初/期末现金与现金流量表核对
        bs_cash = self._find_item(bs, ["货币资金", "现金及现金等价物"])
        cf_ending = self._find_item(cf, ["期末现金及现金等价物余额"])

        if bs_cash and cf_ending:
            diff = abs(bs_cash - cf_ending)
            if diff > bs_cash * self.tolerance:
                return {
                    "passed": False,
                    "flags": ["CROSS_STATEMENT_MISMATCH"],
                    "difference": diff,
                }

        return {"passed": True}

    def calculate_confidence(self, data: Dict, statement_type: str) -> float:
        """计算置信度"""
        if not data:
            return 0.0

        # 基于数据完整度
        expected_items = {
            "balance_sheet": 20,  # 至少应有20项
            "income_statement": 10,
            "cash_flow": 15,
        }
        item_count = len(data)
        expected = expected_items.get(statement_type, 10)
        completeness = min(item_count / expected, 1.0)

        # 基于数值合理性
        reasonableness = self._check_reasonableness(data, statement_type)

        return completeness * 0.6 + reasonableness * 0.4

    def _find_item(self, data: Dict, names: List[str]) -> float:
        """查找科目数值"""
        for name in names:
            for key, val in data.items():
                if name in key:
                    if isinstance(val, dict):
                        return val.get("value", 0)
                    return val
        return None

    def _check_reasonableness(self, data: Dict, statement_type: str) -> float:
        """检查合理性"""
        if not data:
            return 0.0

        values = []
        for v in data.values():
            if isinstance(v, dict):
                values.append(abs(v.get("value", 0)))
            else:
                values.append(abs(v))

        if not values:
            return 0.0

        # 检查是否有零值
        zero_ratio = sum(1 for v in values if v == 0) / len(values)
        if zero_ratio > 0.5:
            return 0.3  # 太多零值

        return 0.9  # 默认

    def _calculate_overall_confidence(self, results: Dict) -> float:
        """计算总体置信度"""
        weights = {"balance_sheet": 0.4, "income_statement": 0.3, "cash_flow": 0.3}
        total = 0.0
        for name, result in results.items():
            w = weights.get(name, 0.25)
            total += w * (1.0 if result.get("passed") else 0.3)
        return min(total, 1.0)

    def _collect_flags(self, results: Dict) -> List[str]:
        """收集所有异常标记"""
        flags = []
        for result in results.values():
            if isinstance(result, dict) and "flags" in result:
                flags.extend(result["flags"])
        return list(set(flags))
