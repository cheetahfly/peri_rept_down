# -*- coding: utf-8 -*-
"""
提取质量报告生成器
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


class QualityReport:
    """财报提取质量报告生成器"""

    def __init__(self, stock_code: str, year: int):
        self.stock_code = stock_code
        self.year = year
        self.generated_at = datetime.now()
        self.statement_results = {}
        self.issues = []
        self.warnings = []

    def add_statement_result(self, statement_type: str, result: Dict, confidence: Dict):
        """添加报表提取结果"""
        self.statement_results[statement_type] = {
            "found": result.get("found", False),
            "item_count": len(result.get("data", {})),
            "pages": result.get("pages", []),
            "confidence": confidence,
        }

        if not result.get("found"):
            self.issues.append(f"{statement_type}: 未找到报表")
            return

        if confidence.get("overall", 0) < 0.8:
            self.warnings.append(
                f"{statement_type}: 置信度 {confidence['overall']:.1%} 低于目标 80%"
            )

        if confidence.get("completeness", 0) < 0.7:
            self.warnings.append(
                f"{statement_type}: 完整性 {confidence['completeness']:.1%} 较低"
            )

        if confidence.get("consistency", 0) < 1.0:
            self.issues.append(
                f"{statement_type}: 数据验证未通过"
            )

        if confidence.get("balance_check", 0) < 0.5:
            self.warnings.append(
                f"{statement_type}: 余额检查未通过或无法验证"
            )

    def generate_report(self) -> str:
        """生成文本报告"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"财报提取质量报告")
        lines.append("=" * 60)
        lines.append(f"股票代码: {self.stock_code}")
        lines.append(f"报告年份: {self.year}")
        lines.append(f"生成时间: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        lines.append("-" * 60)
        lines.append("提取结果汇总")
        lines.append("-" * 60)

        overall_items = 0
        for stmt_type, data in self.statement_results.items():
            lines.append(f"\n{stmt_type}:")
            lines.append(f"  状态: {'成功' if data['found'] else '失败'}")
            lines.append(f"  数据条数: {data['item_count']}")
            lines.append(f"  页数: {len(data['pages'])}")

            conf = data["confidence"]
            lines.append(f"  置信度: {conf.get('overall', 0):.1%}")
            lines.append(f"    - 完整性: {conf.get('completeness', 0):.1%}")
            lines.append(f"    - 一致性: {conf.get('consistency', 0):.1%}")
            lines.append(f"    - 平衡性: {conf.get('balance_check', 0):.1%}")

            overall_items += data["item_count"]

        lines.append(f"\n总数据条数: {overall_items}")

        if self.issues:
            lines.append("")
            lines.append("-" * 60)
            lines.append("问题 (Issues)")
            lines.append("-" * 60)
            for issue in self.issues:
                lines.append(f"  - {issue}")

        if self.warnings:
            lines.append("")
            lines.append("-" * 60)
            lines.append("警告 (Warnings)")
            lines.append("-" * 60)
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        lines.append("")
        lines.append("=" * 60)
        lines.append("改进建议")
        lines.append("=" * 60)

        suggestions = self._generate_suggestions()
        for suggestion in suggestions:
            lines.append(f"  - {suggestion}")

        lines.append("")
        lines.append(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)

    def _generate_suggestions(self) -> List[str]:
        """生成改进建议"""
        suggestions = []

        for stmt_type, data in self.statement_results.items():
            conf = data["confidence"]

            if conf.get("completeness", 0) < 0.7:
                suggestions.append(
                    f"{stmt_type}: 考虑检查是否有跨页表格未正确合并，"
                    "或关键词匹配模式需要扩展"
                )

            if conf.get("balance_check", 0) < 0.5:
                suggestions.append(
                    f"{stmt_type}: 检查报表合计项是否正确提取，"
                    "或验证逻辑是否需要调整"
                )

        if not suggestions:
            suggestions.append("数据质量良好，无需特别改进")

        return suggestions

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "stock_code": self.stock_code,
            "year": self.year,
            "generated_at": self.generated_at.isoformat(),
            "results": self.statement_results,
            "issues": self.issues,
            "warnings": self.warnings,
            "total_items": sum(d["item_count"] for d in self.statement_results.values()),
        }

    def save_report(self, output_dir: str = None) -> str:
        """保存报告到文件"""
        if output_dir is None:
            output_dir = "data/reports"

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        filename = f"{self.stock_code}_{self.year}_quality_report.txt"
        filepath = Path(output_dir) / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.generate_report())

        json_filename = f"{self.stock_code}_{self.year}_quality_report.json"
        json_filepath = Path(output_dir) / json_filename

        with open(json_filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

        return str(filepath)


def generate_quality_report(
    stock_code: str,
    year: int,
    extraction_results: Dict[str, Dict],
    output_dir: str = None
) -> QualityReport:
    """
    生成提取质量报告

    Args:
        stock_code: 股票代码
        year: 报告年份
        extraction_results: 提取结果字典，包含各报表类型的提取结果和置信度
        output_dir: 报告输出目录

    Returns:
        QualityReport实例
    """
    report = QualityReport(stock_code, year)

    for stmt_type, result_data in extraction_results.items():
        if isinstance(result_data, dict):
            result = result_data.get("result", result_data)
            confidence = result_data.get("confidence", {})
            if not confidence:
                confidence = {"overall": 0, "completeness": 0, "consistency": 0, "balance_check": 0}
        else:
            result = result_data
            confidence = {"overall": 0, "completeness": 0, "consistency": 0, "balance_check": 0}

        report.add_statement_result(stmt_type, result, confidence)

    if output_dir:
        report.save_report(output_dir)

    return report