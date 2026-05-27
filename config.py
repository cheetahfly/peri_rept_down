# -*- coding: utf-8 -*-
"""
配置文件
"""

import os

# 基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据存储根目录
DATA_BASE = os.path.join(BASE_DIR, "data")
BY_CODE_DIR = os.path.join(DATA_BASE, "by_code")
BY_INDUSTRY_DIR = os.path.join(DATA_BASE, "by_industry")

# 巨潮资讯网基础URL
CNINFO_BASE_URL = "http://www.cninfo.com.cn"

# 请求相关配置
REQUEST_DELAY = 3  # 请求间隔(秒)
MAX_RETRIES = 3    # 最大重试次数
RETRY_DELAY = 30   # 重试间隔(秒)

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "http://www.cninfo.com.cn",
    "Referer": "http://www.cninfo.com.cn/new/disclosure/stock",
}

# 财报分类关键词映射
REPORT_CATEGORIES = {
    "annual": {
        "name": "年报",
        "category_code": "category_ndbg_szsh",
    },
    "half_year": {
        "name": "半年报",
        "category_code": "category_bndbg_szsh",
    },
    "quarter": {
        "name": "季报",
        "category_code": "category_sjdbf_szsh",
    },
}

# 季报子类型（Q1/Q3通过标题区分）
QUARTER_SUB_TYPES = {
    "quarter_q1": {"name": "一季报", "title_keywords": ["第一季度报告", "一季报", "第一季度"]},
    "quarter_q3": {"name": "三季报", "title_keywords": ["第三季度报告", "三季报", "第三季度"]},
}

# 目标年份范围
TARGET_YEARS = list(range(2022, 2026))  # 2022-2025

# 文件名中的分类名到内部类型的映射
CATEGORY_NAME_TO_TYPE = {
    "年报": "annual",
    "半年报": "half_year",
    "一季报": "quarter_q1",
    "三季报": "quarter_q3",
    "季度报告": "quarter_q1",  # 兼容旧命名
}

# User-Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# 日志配置
LOG_FILE = os.path.join(BASE_DIR, "crawler.log")
