# tests/test_semantic_recovery.py
def test_vocabulary_loaded():
    """测试词汇库已加载"""
    from extraction.semantic_recovery import SemanticRecovery
    recovery = SemanticRecovery()
    assert "balance_sheet" in recovery.vocabulary
    assert len(recovery.vocabulary["balance_sheet"]) > 50

def test_context_inference():
    """测试上下文推断"""
    from extraction.semantic_recovery import SemanticRecovery
    from extraction.cas_vocabulary import BALANCE_SHEET_ITEMS
    recovery = SemanticRecovery()
    texts = ["资产", "负债", "权益", "货币资金"]
    result = recovery._infer_item_name_from_context(texts, set(BALANCE_SHEET_ITEMS))
    assert result in BALANCE_SHEET_ITEMS

def test_numeric_parsing():
    """测试数值解析"""
    from extraction.semantic_recovery import SemanticRecovery
    recovery = SemanticRecovery()
    assert recovery._parse_numeric("1,234,567") == 1234567
    assert recovery._parse_numeric("(1,234)") == -1234
    assert recovery._parse_numeric("") == 0

def test_is_numeric():
    """测试数值判断"""
    from extraction.semantic_recovery import SemanticRecovery
    recovery = SemanticRecovery()
    assert recovery._is_numeric("1,234,567") == True
    assert recovery._is_numeric("(1,234)") == True
    assert recovery._is_numeric("货币资金") == False