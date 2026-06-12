# -*- coding: utf-8 -*-
"""
Tri-channel CF 对比工具库：tushare vs RDS 现金流/三表对比。

复用 scripts/dual_channel_cf_lib.py 的 normalize/extract/best_match 逻辑，
新增 tushare 提取与三渠道匹配。
"""
from typing import Dict, List

import pandas as pd

from astock_fundamentals.sources.api import TushareProvider
