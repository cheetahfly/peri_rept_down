# -*- coding: utf-8 -*-
"""
数据分类存储模块
"""

import os
import shutil
import json
from typing import Dict, List


# 行业分类映射 - 根据股票代码范围大致分类
# 实际项目中应使用更精确的行业数据
INDUSTRY_MAPPING = {
    # 银行
    "000001": "银行",
    "600000": "银行",
    "600015": "银行",
    "600016": "银行",
    "600036": "银行",
    "601009": "银行",
    "601166": "银行",
    "601169": "银行",
    "601229": "银行",
    "601288": "银行",
    "601328": "银行",
    "601398": "银行",
    "601818": "银行",
    "601939": "银行",
    "601988": "银行",
    "601998": "银行",
    "601997": "银行",
    "600926": "银行",
    # 保险
    "601318": "保险",
    "601336": "保险",
    "601628": "保险",
    "601601": "保险",
    "601319": "保险",
    # 证券
    "600030": "证券",
    "600837": "证券",
    "600999": "证券",
    "601066": "证券",
    "601088": "证券",
    "601155": "房地产",
    "000002": "房地产",
    "600048": "房地产",
    "600340": "房地产",
    "600383": "房地产",
    "000024": "房地产",
    "600649": "房地产",
    "601588": "房地产",
    # 制造业 - 默认
}


def get_industry_by_stock_code(stock_code: str) -> str:
    """
    根据股票代码获取行业分类

    Args:
        stock_code: 股票代码

    Returns:
        行业名称
    """
    # 精确匹配
    if stock_code in INDUSTRY_MAPPING:
        return INDUSTRY_MAPPING[stock_code]

    # 根据代码范围匹配
    code_prefix = stock_code[:6]

    # 银行 (600xxx, 000xxx 开头)
    if code_prefix.startswith(("600", "000")):
        code_num = int(stock_code[3:6]) if len(stock_code) >= 6 else 0

        # 国有大银行
        if stock_code in ["601398", "601988", "601328", "601288", "601939", "601166"]:
            return "银行"
        # 股份制银行
        if 1 <= code_num <= 99:
            return "银行"

    # 默认归类为制造业
    return "制造业"


def generate_file_name(report: Dict) -> str:
    """
    生成文件名

    Args:
        report: 财报信息字典

    Returns:
        文件名
    """
    stock_code = report.get("stock_code", "unknown")
    stock_name = report.get("stock_name", "unknown")
    category = report.get("category", "")
    category_name = report.get("category_name", "")
    year = report.get("report_year", "unknown")
    announcement_id = report.get("announcement_id", "")

    # 获取文件扩展名
    url = report.get("announcement_url", "")
    if url.endswith(".pdf"):
        ext = ".pdf"
    elif url.endswith(".html") or url.endswith(".htm"):
        ext = ".html"
    else:
        ext = ".pdf"  # 默认pdf

    # 格式: 股票代码_公司名称_年份_报告类型.扩展名
    safe_name = stock_name.replace("*", "_").replace("/", "_").replace("\\", "_")
    file_name = f"{stock_code}_{safe_name}_{year}_{category_name}{ext}"

    return file_name


class DataClassifier:
    """数据分类器 - 双重分类存储"""

    def __init__(self, by_code_dir: str, by_industry_dir: str):
        """
        初始化分类器

        Args:
            by_code_dir: 按股票代码存储的目录
            by_industry_dir: 按行业存储的目录
        """
        self.by_code_dir = by_code_dir
        self.by_industry_dir = by_industry_dir

        # 确保目录存在
        os.makedirs(by_code_dir, exist_ok=True)
        os.makedirs(by_industry_dir, exist_ok=True)

    def get_by_code_path(self, stock_code: str, file_name: str) -> str:
        """
        获取按股票代码存储的路径

        Args:
            stock_code: 股票代码
            file_name: 文件名

        Returns:
            完整路径
        """
        stock_dir = os.path.join(self.by_code_dir, stock_code)
        os.makedirs(stock_dir, exist_ok=True)
        return os.path.join(stock_dir, file_name)

    def get_by_industry_path(self, report: Dict) -> str:
        """
        获取按行业存储的路径

        Args:
            report: 财报信息字典

        Returns:
            完整路径
        """
        stock_code = report.get("stock_code", "unknown")
        industry = get_industry_by_stock_code(stock_code)
        file_name = generate_file_name(report)

        industry_dir = os.path.join(self.by_industry_dir, industry)
        os.makedirs(industry_dir, exist_ok=True)

        return os.path.join(industry_dir, file_name)

    def classify_and_save(self, report: Dict, source_path: str = None) -> Dict:
        """
        分类存储财报

        Args:
            report: 财报信息字典
            source_path: 源文件路径(如果已下载)

        Returns:
            存储结果
        """
        stock_code = report.get("stock_code", "unknown")
        file_name = generate_file_name(report)

        results = {}

        # 按股票代码存储
        by_code_path = self.get_by_code_path(stock_code, file_name)
        if source_path and os.path.exists(source_path) and source_path != by_code_path:
            try:
                shutil.copy2(source_path, by_code_path)
            except PermissionError:
                # Windows文件句柄未关闭，等待后重试
                import time
                time.sleep(1)
                shutil.copy2(source_path, by_code_path)
            results["by_code"] = by_code_path
        else:
            results["by_code"] = by_code_path

        # 按行业存储
        by_industry_path = self.get_by_industry_path(report)
        if source_path and os.path.exists(source_path) and source_path != by_industry_path:
            if not os.path.exists(by_industry_path):
                try:
                    shutil.copy2(source_path, by_industry_path)
                except PermissionError:
                    import time
                    time.sleep(1)
                    shutil.copy2(source_path, by_industry_path)
            results["by_industry"] = by_industry_path
        else:
            results["by_industry"] = by_industry_path

        return results

    def save_metadata(self, reports: List[Dict], meta_file: str = None) -> str:
        """
        保存财报元数据到JSON文件

        Args:
            reports: 财报列表
            meta_file: 元数据文件路径

        Returns:
            保存的路径
        """
        if meta_file is None:
            meta_file = os.path.join(self.by_code_dir, "metadata.json")

        os.makedirs(os.path.dirname(meta_file), exist_ok=True)

        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)

        return meta_file

    def load_metadata(self, meta_file: str = None) -> List[Dict]:
        """
        加载财报元数据

        Args:
            meta_file: 元数据文件路径

        Returns:
            财报列表
        """
        if meta_file is None:
            meta_file = os.path.join(self.by_code_dir, "metadata.json")

        if not os.path.exists(meta_file):
            return []

        with open(meta_file, "r", encoding="utf-8") as f:
            return json.load(f)


def test():
    """测试函数"""
    classifier = DataClassifier(
        by_code_dir="./data/by_code",
        by_industry_dir="./data/by_industry"
    )

    report = {
        "stock_code": "000001",
        "stock_name": "平安银行",
        "category": "annual",
        "category_name": "年报",
        "report_year": 2023,
        "announcement_url": "http://example.com/test.pdf",
        "announcement_id": "12345",
    }

    file_name = generate_file_name(report)
    print(f"Generated file name: {file_name}")

    industry = get_industry_by_stock_code("000001")
    print(f"Industry: {industry}")

    by_code_path = classifier.get_by_code_path("000001", file_name)
    print(f"By code path: {by_code_path}")


if __name__ == "__main__":
    test()
