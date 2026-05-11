# extraction/engine_validator.py
from typing import Dict, List, Tuple
from collections import Counter


class EngineValidator:
    """多引擎交叉验证器"""

    def __init__(self, threshold: float = 0.95):
        self.threshold = threshold

    def check_consistency(self, result1: Dict, result2: Dict) -> float:
        """检查两个引擎结果的一致性"""
        if not result1 or not result2:
            return 0.0

        common_keys = set(result1.keys()) & set(result2.keys())
        if not common_keys:
            return 0.0

        matches = 0
        for key in common_keys:
            v1 = self._get_value(result1[key])
            v2 = self._get_value(result2[key])
            if v1 and v2 and self._values_match(v1, v2):
                matches += 1

        return matches / len(common_keys)

    def resolve(self, engine_results: List[Dict]) -> Dict:
        """多引擎结果仲裁"""
        if len(engine_results) == 1:
            return engine_results[0]

        # 收集所有数据项
        all_items = {}
        for result in engine_results:
            data = result.get("data", result)
            for key, val in data.items():
                if key not in all_items:
                    all_items[key] = []
                all_items[key].append({
                    "value": self._get_value(val),
                    "method": result.get("method", "unknown"),
                })

        # 仲裁
        resolved_data = {}
        for key, values in all_items.items():
            resolved_data[key] = self._arbitrate(values)

        return {
            "data": resolved_data,
            "method": "engine_validator",
            "engine_count": len(engine_results),
        }

    def _get_value(self, val) -> float:
        """提取数值"""
        if isinstance(val, dict):
            return val.get("value", 0)
        return val if isinstance(val, (int, float)) else 0

    def _values_match(self, v1: float, v2: float, tolerance: float = 0.01) -> bool:
        """判断两个值是否匹配"""
        if v1 == 0 and v2 == 0:
            return True
        if v1 == 0 or v2 == 0:
            return False
        return abs(v1 - v2) / max(abs(v1), abs(v2)) <= tolerance

    def _arbitrate(self, values: List[Dict]) -> float:
        """仲裁选择最佳值"""
        # 过滤无效值
        valid = [v["value"] for v in values if v["value"] is not None]
        if not valid:
            return 0

        # 多数一致
        counts = Counter([round(v, 2) for v in valid])
        most_common = counts.most_common(1)
        if most_common and most_common[0][1] > 1:
            return most_common[0][0]

        # 加权平均(pdfplumber优先)
        weights = {"pdfplumber": 1.0, "pymupdf": 0.9, "pdf2htmlEX": 0.8, "ocr": 0.7}
        total_weight = 0
        weighted_sum = 0
        for v in values:
            w = weights.get(v["method"], 0.5)
            total_weight += w
            weighted_sum += v["value"] * w

        return weighted_sum / total_weight if total_weight > 0 else valid[0]