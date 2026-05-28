import yaml
import os

def test_aliases_structure():
    """Verify aliases.yaml hierarchical structure"""
    path = os.path.join(os.path.dirname(__file__), '..', 'rules', 'aliases.yaml')
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    for statement_type in ['balance_sheet', 'income_statement', 'cash_flow']:
        assert statement_type in data, f"Missing {statement_type}"
        for report_type in ['annual', 'half_year', 'quarter_q1', 'quarter_q3']:
            assert report_type in data[statement_type], \
                f"Missing {report_type} in {statement_type}"
            # Verify it's a dict with items
            assert isinstance(data[statement_type][report_type], dict), \
                f"{statement_type}.{report_type} should be a dict"

def test_aliases_items_exist():
    """Verify key items still exist after migration"""
    path = os.path.join(os.path.dirname(__file__), '..', 'rules', 'aliases.yaml')
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # Check some key items in income_statement.annual
    is_annual = data['income_statement']['annual']
    assert '营业收入' in is_annual
    assert '利息收入' in is_annual

    # Check some key items in balance_sheet.annual
    bs_annual = data['balance_sheet']['annual']
    assert '资产总计' in bs_annual

    # Check cash_flow.annual
    cf_annual = data['cash_flow']['annual']
    assert '经营活动产生的现金流量净额' in cf_annual
