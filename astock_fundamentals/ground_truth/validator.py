# -*- coding: utf-8 -*-
"""
财务报表逻辑关系校验引擎

基于 rules/validation_rules.yaml 中定义的勾稽关系，对提取的财务数据
进行加减逻辑审核。输出通过/未通过的报告。
"""
import os, yaml, re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "rules")
RULES_FILE = os.path.join(RULES_DIR, "validation_rules.yaml")


@dataclass
class ValidationResult:
    equation: str
    left_value: Optional[float]
    right_value: Optional[float]
    diff: Optional[float]
    diff_pct: Optional[float]
    passed: bool
    severity: str  # pass / warn / fail


class FinancialValidator:
    def __init__(self, decode_maps: Dict[str, Dict[str, str]] = None):
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            self.rules = yaml.safe_load(f)
        self._decode_maps = decode_maps or {}  # {st: {code: name}}

    def validate(self, statement_type: str, data: Dict[str, float],
                 all_data: Dict[str, Dict[str, float]] = None) -> List[ValidationResult]:
        """
        校验单张报表数据。

        Args:
            statement_type: balance_sheet / income_statement / cash_flow
            data: {科目名: 数值} 或 {field_code: 数值}
            all_data: 跨表校验时需要所有三张表的数据 {st: {name: value}}
        """
        rules = self.rules.get(statement_type, [])
        if not rules:
            return []

        results = []
        tol = self.rules.get("default_tolerance", 0.01)

        for rule in rules:
            try:
                lt = self._eval_field(rule.get("left", ""), data, all_data, st=statement_type)
                rt = self._eval_field(rule.get("right", ""), data, all_data, st=statement_type)
            except (KeyError, ValueError, ZeroDivisionError):
                results.append(ValidationResult(
                    equation=rule.get("equation", "?"),
                    left_value=None, right_value=None,
                    diff=None, diff_pct=None, passed=False, severity="skip"
                ))
                continue

            if lt is None or rt is None:
                results.append(ValidationResult(
                    equation=rule.get("equation", "?"),
                    left_value=lt, right_value=rt,
                    diff=None, diff_pct=None, passed=False, severity="skip"
                ))
                continue

            rule_tol = rule.get("tolerance", tol)
            strict = rule.get("strict", False)

            diff = lt - rt
            denom = max(abs(lt), abs(rt), 1)
            diff_pct = abs(diff) / denom if denom > 0 else None

            passed = diff_pct is not None and diff_pct <= rule_tol
            severity = "pass" if passed else ("fail" if strict else "warn")

            results.append(ValidationResult(
                equation=rule.get("equation", ""),
                left_value=lt, right_value=rt,
                diff=diff, diff_pct=diff_pct,
                passed=passed, severity=severity
            ))

        return results

    def validate_all(self, data: Dict[str, Dict[str, float]]) -> List[ValidationResult]:
        """校验三大表 + 跨表关系"""
        results = []
        for st in ["balance_sheet", "income_statement", "cash_flow"]:
            if st in data:
                results.extend(self.validate(st, data[st], data))
        if data:
            results.extend(self._check_cross(data))
        return results

    def _check_cross(self, data: Dict[str, Dict[str, float]]) -> List[ValidationResult]:
        """跨表校验"""
        results = []
        cross = self.rules.get("cross_statement", [])
        for rule in cross:
            try:
                left_expr = rule.get("left", "")
                right_expr = rule.get("right", "")

                lt = None
                rt = None

                # Parse "BS:F006N" style or direct expressions
                for expr, store in [(left_expr, "L"), (right_expr, "R")]:
                    val = None
                    for st, prefix in [("balance_sheet", "BS"), ("income_statement", "IS"), ("cash_flow", "CF")]:
                        if f"{prefix}:" in expr:
                            field = expr.replace(f"{prefix}:", "")
                            if st in data and field in data[st]:
                                val = data[st][field]
                            break
                    if val is None:
                        val = self._eval_field(expr, data.get("balance_sheet", {}), data)

                    if store == "L":
                        lt = val
                    else:
                        rt = val

                if lt is None or rt is None:
                    continue

                diff = lt - rt
                denom = max(abs(lt), abs(rt), 1)
                diff_pct = abs(diff) / denom
                passed = diff_pct <= rule.get("tolerance", 0.05)

                results.append(ValidationResult(
                    equation=rule.get("equation", ""),
                    left_value=lt, right_value=rt, diff=diff,
                    diff_pct=diff_pct, passed=passed,
                    severity="pass" if passed else "warn"
                ))
            except (KeyError, ValueError):
                continue
        return results

    def _code_to_name(self, code: str, st: str = "balance_sheet") -> str:
        """Translate RDS field code (F038N) to Chinese name via decode map"""
        st_map = self._decode_maps.get(st, {})
        return st_map.get(code, code)

    def _eval_field(self, expr: str, data: Dict[str, float],
                    all_data: Dict[str, Dict[str, float]] = None, st: str = "balance_sheet") -> Optional[float]:
        """Evaluate a field expression (single code or arithmetic)"""
        if not expr or not data:
            return None

        expr = str(expr).strip()
        # Simple single field code - translate to Chinese name
        if re.match(r'^[A-Z]\d{3}[A-Z]$', expr):
            name = self._code_to_name(expr, st)
            return data.get(name) if name != expr else data.get(expr)
        # Cross-table reference like BS:F006N
        cross_match = re.match(r'^(BS|IS|CF):(.+)$', expr)
        if cross_match and all_data:
            st_map = {"BS": "balance_sheet", "IS": "income_statement", "CF": "cash_flow"}
            st = st_map.get(cross_match.group(1))
            field = cross_match.group(2)
            if st and st in all_data and field in all_data[st]:
                return all_data[st][field]
            return None

        # Arithmetic expression: "F006N + F007N - F008N"
        # Replace field codes with values
        parts = re.split(r'(\s*[+\-]\s*)', expr)
        result = 0.0
        op = "+"
        for part in parts:
            part = part.strip()
            if part in ("+", "-"):
                op = part
                continue
            if not part:
                continue
            # Try field code match
            val = None
            if re.match(r'^[A-Z]\d{3}[A-Z]$', part):
                name = self._code_to_name(part, st)
                val = data.get(name) if name != part else data.get(part)
            elif part.startswith("BS:") or part.startswith("IS:") or part.startswith("CF:"):
                if all_data:
                    st_map = {"BS": "balance_sheet", "IS": "income_statement", "CF": "cash_flow"}
                    prefix, field = part.split(":", 1)
                    st = st_map.get(prefix)
                    val = all_data.get(st, {}).get(field) if st else None
            else:
                # Try by name
                val = data.get(part)

            if val is None:
                continue

            if op == "+":
                result += val
            else:
                result -= val

        return result if result != 0 or any(data.get(p) for p in re.findall(r'[A-Z]\d{3}[A-Z]', expr)) else None

    def summary_report(self, results: List[ValidationResult]) -> str:
        """Generate a text summary of validation results"""
        total = len(results)
        passed = sum(1 for r in results if r.severity == "pass")
        failed = sum(1 for r in results if r.severity == "fail")
        warned = sum(1 for r in results if r.severity == "warn")
        skipped = sum(1 for r in results if r.severity == "skip")
        return (f"Validation: {total} rules | {passed} passed, {failed} failed, "
                f"{warned} warned, {skipped} skipped | "
                f"Pass rate: {passed/(total-skipped)*100:.0f}%" if (total-skipped) > 0 else "No applicable rules")
