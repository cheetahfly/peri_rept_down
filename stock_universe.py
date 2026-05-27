# -*- coding: utf-8 -*-
"""
股票池配置 - 跨行业A股上市公司
"""

# 20只跨行业股票（含沪市深市、不同板块）
STOCK_UNIVERSE = [
    # 银行
    {"code": "000001", "name": "平安银行", "industry": "银行", "exchange": "SZSE"},
    {"code": "600036", "name": "招商银行", "industry": "银行", "exchange": "SSE"},
    # 保险
    {"code": "601318", "name": "中国平安", "industry": "保险", "exchange": "SSE"},
    # 房地产
    {"code": "000002", "name": "万科A", "industry": "房地产", "exchange": "SZSE"},
    # 白酒
    {"code": "000858", "name": "五粮液", "industry": "白酒", "exchange": "SZSE"},
    {"code": "600519", "name": "贵州茅台", "industry": "白酒", "exchange": "SSE"},
    # 人工智能
    {"code": "002230", "name": "科大讯飞", "industry": "人工智能", "exchange": "SZSE"},
    # 消费电子
    {"code": "002475", "name": "立讯精密", "industry": "消费电子", "exchange": "SZSE"},
    # 工程机械
    {"code": "600031", "name": "三一重工", "industry": "工程机械", "exchange": "SSE"},
    # 建材
    {"code": "600585", "name": "海螺水泥", "industry": "建材", "exchange": "SSE"},
    # 乳制品
    {"code": "600887", "name": "伊利股份", "industry": "乳制品", "exchange": "SSE"},
    # 安防
    {"code": "002415", "name": "海康威视", "industry": "安防", "exchange": "SZSE"},
    # 新能源电池
    {"code": "300750", "name": "宁德时代", "industry": "新能源电池", "exchange": "SZSE"},
    # 证券
    {"code": "600030", "name": "中信证券", "industry": "证券", "exchange": "SSE"},
    # 石油
    {"code": "601857", "name": "中国石油", "industry": "石油", "exchange": "SSE"},
    # 建筑
    {"code": "601668", "name": "中国建筑", "industry": "建筑", "exchange": "SSE"},
    # 医药
    {"code": "600196", "name": "复星医药", "industry": "医药", "exchange": "SSE"},
    # 金融IT
    {"code": "603501", "name": "同花顺", "industry": "金融IT", "exchange": "SSE"},
    # 家电
    {"code": "000651", "name": "格力电器", "industry": "家电", "exchange": "SZSE"},
    # 汽车
    {"code": "002594", "name": "比亚迪", "industry": "汽车", "exchange": "SZSE"},
]


def get_stock_by_code(code: str) -> dict:
    """根据股票代码获取配置"""
    for s in STOCK_UNIVERSE:
        if s["code"] == code:
            return s
    return None


def get_stocks_by_industry(industry: str) -> list:
    """根据行业筛选股票"""
    return [s for s in STOCK_UNIVERSE if s["industry"] == industry]


def get_all_codes() -> list:
    """获取所有股票代码"""
    return [s["code"] for s in STOCK_UNIVERSE]
