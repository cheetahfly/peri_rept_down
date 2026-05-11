# tests/test_cas_mapper.py
def test_map_standard_items():
    """测试标准科目映射"""
    from extraction.cas_mapper import ChartOfAccountsMapper
    mapper = ChartOfAccountsMapper()
    result = mapper.map_item("货币资金", "balance_sheet")
    assert result['cas_code'] == "1001"
    assert result['cas_name'] == "货币资金"

def test_map_company_variant():
    """测试公司变体映射"""
    from extraction.cas_mapper import ChartOfAccountsMapper
    mapper = ChartOfAccountsMapper()
    # "货币及现金等价物" 应映射到 "货币资金"
    result = mapper.map_item("货币及现金等价物", "balance_sheet")
    assert result['cas_name'] == "货币资金"

def test_industry_variant():
    """测试银行业变体"""
    from extraction.cas_mapper import ChartOfAccountsMapper
    mapper = ChartOfAccountsMapper(industry="bank")
    result = mapper.map_item("存放中央银行款项", "balance_sheet")
    assert result['cas_code'] == "1002"

def test_map_statement():
    """测试整表映射"""
    from extraction.cas_mapper import ChartOfAccountsMapper
    mapper = ChartOfAccountsMapper()
    data = {
        "货币资金": 1234567890,
        "应收账款": 987654321,
    }
    result = mapper.map_statement(data, "balance_sheet")
    assert "货币资金" in result
    assert result["货币资金"]["value"] == 1234567890
    assert result["货币资金"]["cas_code"] == "1001"
