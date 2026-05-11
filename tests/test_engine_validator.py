# tests/test_engine_validator.py
import pytest


def test_cross_engine_validation():
    """测试双引擎结果一致性验证"""
    from extraction.engine_validator import EngineValidator
    validator = EngineValidator()

    # pdfplumber结果
    result1 = {"货币资金": 123456, "应收账款": 78901}
    # PyMuPDF结果
    result2 = {"货币资金": 123456, "应收账款": 78901}

    consistency = validator.check_consistency(result1, result2)
    assert consistency == 1.0  # 完全一致


def test_mismatch_detection():
    """测试不一致检测"""
    from extraction.engine_validator import EngineValidator
    validator = EngineValidator()

    result1 = {"货币资金": 123456}
    result2 = {"货币资金": 999999}  # 不一致

    consistency = validator.check_consistency(result1, result2)
    assert consistency == 0.0  # 完全不一致


def test_conflict_resolution():
    """测试冲突仲裁"""
    from extraction.engine_validator import EngineValidator
    validator = EngineValidator()
    results = [
        {"method": "pdfplumber", "data": {"A": 100}},
        {"method": "PyMuPDF", "data": {"A": 100}},
        {"method": "pdf2htmlEX", "data": {"A": 95}},
    ]
    resolved = validator.resolve(results)
    assert resolved["data"]["A"] == 100  # 多数一致
    assert resolved["engine_count"] == 3


def test_weighted_average():
    """测试加权平均"""
    from extraction.engine_validator import EngineValidator
    validator = EngineValidator()
    results = [
        {"method": "pdfplumber", "data": {"A": 100}},
        {"method": "pymupdf", "data": {"A": 90}},
        {"method": "ocr", "data": {"A": 80}},
    ]
    resolved = validator.resolve(results)
    # pdfplumber权重1.0, pymupdf权重0.9, ocr权重0.7
    # (100*1.0 + 90*0.9 + 80*0.7) / (1.0+0.9+0.7) = 237/2.6 = 91.15
    assert resolved["data"]["A"] == pytest.approx(91.15, abs=0.01)