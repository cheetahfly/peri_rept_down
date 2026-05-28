import yaml
import os

def test_field_order_loads():
    path = os.path.join(os.path.dirname(__file__), '..', 'rules', 'field_order.yaml')
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    assert 'income_statement' in data
    assert 'balance_sheet' in data
    assert 'cash_flow' in data

    # Verify F033N and F063N have different order in income_statement
    assert data['income_statement']['F033N'] != data['income_statement']['F063N']
    assert data['income_statement']['F033N'] < data['income_statement']['F063N']

    # Verify all sections have integer values
    for section in ['income_statement', 'balance_sheet', 'cash_flow']:
        for key, val in data[section].items():
            assert isinstance(val, int), f"{section}.{key} should be int"
