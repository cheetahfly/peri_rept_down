"""Shared test fixtures for EM evaluation tests."""
import pytest


@pytest.fixture
def sample_stock_list():
    """A small stock list spanning all 4 boards."""
    return [
        "600000", "600001", "601000", "603000",  # 沪市主板
        "000001", "000002", "002001",            # 深市主板
        "300001", "300002", "301001",            # 创业板
        "688001", "688002", "689001",            # 科创板
    ]


@pytest.fixture
def fake_em_balance_sheet_df():
    """A fake balance sheet DataFrame mimicking AKShare EM output."""
    import pandas as pd
    return pd.DataFrame({
        "REPORT_DATE": ["2022-03-31", "2022-06-30", "2022-09-30", "2022-12-31"],
        "货币资金": [100.0, 110.0, 120.0, 130.0],
        "应收账款": [50.0, 55.0, 60.0, 65.0],
    })


@pytest.fixture
def fake_em_cash_flow_df_with_yi_suffix():
    """Cash flow DataFrame with 亿 suffix on values."""
    import pandas as pd
    return pd.DataFrame({
        "REPORT_DATE": ["2022-12-31"],
        "经营活动产生的现金流量净额": ["100.50亿"],
    })