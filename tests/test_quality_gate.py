# tests/test_quality_gate.py
def test_balance_sheet_check():
    """测试资产负债表平衡校验"""
    from extraction.quality_gate import QualityGate
    gate = QualityGate()
    data = {
        "资产总计": 1000000,
        "负债合计": 600000,
        "股东权益合计": 400000,
    }
    result = gate.validate_balance_sheet(data)
    assert result["passed"] == True

def test_balance_sheet_fail():
    """测试不平衡情况"""
    from extraction.quality_gate import QualityGate
    gate = QualityGate()
    data = {
        "资产总计": 1000000,
        "负债合计": 600000,
        "股东权益合计": 300000,  # 不平衡
    }
    result = gate.validate_balance_sheet(data)
    assert result["passed"] == False
    assert "BALANCE_CHECK_FAILED" in result["flags"]

def test_confidence_calculation():
    """测试置信度计算"""
    from extraction.quality_gate import QualityGate
    gate = QualityGate()
    data = {
        "资产总计": 1000000,
        "货币资金": 500000,
        "应收账款": 300000,
        "短期借款": 200000,
    }
    confidence = gate.calculate_confidence(data, statement_type="balance_sheet")
    assert 0 <= confidence <= 1

def test_missing_items():
    """测试缺失项目"""
    from extraction.quality_gate import QualityGate
    gate = QualityGate()
    data = {
        "资产总计": 1000000,
        # 缺少负债和权益
    }
    result = gate.validate_balance_sheet(data)
    assert result["passed"] == False
    assert result["reason"] == "missing_items"
