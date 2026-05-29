# -*- coding: utf-8 -*-
"""
全局配置 - 统一管理项目路径、请求设置、数据源参数。
原提取config保留在 astock_fundamentals.core.extraction_config
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AStockConfig:
    """主配置类"""
    # 项目根目录
    project_root: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 数据目录
    data_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data"
    ))

    # RDS 数据库路径
    rds_data_dir: str = "D:/Research/Quant/SETL/cninfo/data_backup"

    # 公告下载配置
    pdf_data_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "pdfs"
    ))
    extracted_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "extracted"
    ))

    # 规则文件目录
    rules_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "rules"
    ))

    # 请求配置
    request_delay: float = 0.5
    max_retries: int = 3
    user_agents: List[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    ])


_default_config = None


def get_config() -> AStockConfig:
    global _default_config
    if _default_config is None:
        _default_config = AStockConfig()
    return _default_config
