# -*- coding: utf-8 -*-
"""
主程序 - A股上市公司定期财报爬虫
"""

import os
import sys
import json
import time
import random
from datetime import datetime
from typing import Dict, List

# 导入项目模块
from config import (
    CNINFO_BASE_URL,
    BY_CODE_DIR,
    BY_INDUSTRY_DIR,
    REQUEST_DELAY,
)
from crawlers.stock_list import StockListCrawler
from crawlers.report_list import ReportListCrawler
from crawlers.downloader import ReportDownloader
from storage.classifier import DataClassifier, generate_file_name


class FinancialReportCrawler:
    """财报爬虫主类"""

    def __init__(self):
        self.stock_crawler = StockListCrawler()
        self.report_crawler = ReportListCrawler()
        self.downloader = ReportDownloader()
        self.classifier = DataClassifier(BY_CODE_DIR, BY_INDUSTRY_DIR)

        # 元数据文件
        self.metadata_file = os.path.join(BY_CODE_DIR, "metadata.json")

    def load_processed_stocks(self) -> set:
        """加载已处理的股票代码"""
        metadata = self.classifier.load_metadata(self.metadata_file)
        processed = set()
        for item in metadata:
            if "stock_code" in item:
                processed.add(item["stock_code"])
        return processed

    def save_metadata(self, reports: list):
        """保存元数据"""
        # 加载现有数据
        existing = []
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                existing = json.load(f)

        # 添加新数据
        existing_ids = {r.get("announcement_id") for r in existing}
        for report in reports:
            if report.get("announcement_id") not in existing_ids:
                existing.append(report)

        # 保存
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def get_save_path(self, report: Dict) -> str:
        """
        获取保存路径

        Args:
            report: 财报信息

        Returns:
            保存路径
        """
        stock_code = report.get("stock_code", "unknown")
        file_name = generate_file_name(report)
        return os.path.join(BY_CODE_DIR, stock_code, file_name)

    def crawl_all_stocks(self, test_mode: bool = False, test_count: int = 10):
        """
        爬取所有股票财报

        Args:
            test_mode: 是否测试模式(只爬取少量数据)
            test_count: 测试模式下的股票数量
        """
        print("=" * 60)
        print("A股上市公司定期财报爬虫")
        print("=" * 60)

        # 获取股票列表
        print("\n[1/4] 获取股票列表...")
        stocks = self.stock_crawler.get_all_stocks()

        if not stocks:
            print("获取股票列表失败")
            return

        print(f"获取到 {len(stocks)} 家上市公司")

        # 过滤A股 (股票代码以 000, 001, 002, 003, 300, 600, 601, 603, 688 开头)
        a_share_stocks = [
            s for s in stocks
            if s.get("stockCode") and any(
                s["stockCode"].startswith(prefix)
                for prefix in ["000", "001", "002", "003", "300", "600", "601", "603", "688"]
            )
        ]
        print(f"其中A股上市公司 {len(a_share_stocks)} 家")

        # 如果是测试模式，只取前几个
        if test_mode:
            a_share_stocks = a_share_stocks[:test_count]
            print(f"测试模式: 只处理 {test_count} 家公司")

        # 加载已处理的股票
        processed_stocks = self.load_processed_stocks()
        print(f"已处理 {len(processed_stocks)} 家公司")

        # 遍历每家公司
        total_reports = 0
        for i, stock in enumerate(a_share_stocks):
            stock_code = stock.get("stockCode", "")
            org_id = stock.get("orgId", "")
            company_name = stock.get("securityName", stock.get("companyName", ""))

            # 跳过已处理的
            if stock_code in processed_stocks:
                print(f"[{i+1}/{len(a_share_stocks)}] 跳过 {stock_code} {company_name} (已处理)")
                continue

            print(f"\n[{i+1}/{len(a_share_stocks)}] 处理 {stock_code} {company_name}...")

            # 获取财报列表
            print("  获取财报列表...")
            reports = self.report_crawler.get_all_reports(org_id, stock_code, company_name)

            if not reports:
                print("  未找到财报")
                time.sleep(REQUEST_DELAY)
                continue

            print(f"  找到 {len(reports)} 条财报记录")

            # 保存元数据
            self.save_metadata(reports)
            total_reports += len(reports)

            # 下载文件
            print("  开始下载...")
            for j, report in enumerate(reports):
                file_path = self.get_save_path(report)

                if os.path.exists(file_path):
                    print(f"    [{j+1}/{len(reports)}] 跳过 (已存在)")
                    continue

                url = report.get("announcement_url")
                if url:
                    if self.downloader.download_file(url, file_path):
                        # 复制到行业目录
                        self.classifier.classify_and_save(report, file_path)
                    time.sleep(REQUEST_DELAY + random.uniform(0, 2))

            # 标记为已处理
            processed_stocks.add(stock_code)

            print(f"  完成")

            # 随机延迟
            time.sleep(REQUEST_DELAY + random.uniform(0, 3))

        print("\n" + "=" * 60)
        print(f"爬取完成! 共处理 {len(processed_stocks)} 家公司, {total_reports} 条财报")
        print("=" * 60)

    def test_single_stock(self, stock_code: str = "000001"):
        """
        测试单只股票

        Args:
            stock_code: 股票代码
        """
        print(f"测试股票: {stock_code}")

        # 常用股票的 orgId 映射 (可以直接查询获取，这里简化处理)
        # 000001 平安银行: gssz0000001
        # 000002 万科A: gssz0000002
        org_id_map = {
            "000001": ("gssz0000001", "平安银行"),
            "000002": ("gssz0000002", "万科A"),
            "600000": ("gssz0600000", "浦发银行"),
            "600036": ("gssz0600036", "招商银行"),
        }

        if stock_code in org_id_map:
            org_id, company_name = org_id_map[stock_code]
        else:
            # 动态查询
            print("正在查询股票信息...")
            stocks = self.stock_crawler.get_all_stocks()
            stock = next((s for s in stocks if s.get("stockCode") == stock_code), None)

            if not stock:
                print(f"未找到股票 {stock_code}")
                return

            org_id = stock.get("orgId", "")
            company_name = stock.get("securityName", stock.get("companyName", ""))

        print(f"公司名称: {company_name}")
        print(f"OrgId: {org_id}")

        # 获取财报列表
        reports = self.report_crawler.get_all_reports(org_id, stock_code, company_name)

        # 过滤掉摘要类公告，只保留正式财报
        original_count = len(reports)
        reports = [r for r in reports if "摘要" not in r.get("announcement_title", "")]
        print(f"\n找到 {original_count} 条公告，过滤后保留 {len(reports)} 条财报")

        print(f"开始下载前5条...")

        # 下载前5条财报
        for i, report in enumerate(reports[:5]):
            file_path = self.get_save_path(report)
            url = report.get("announcement_url")

            print(f"[{i+1}/5] 下载: {report.get('announcement_title')[:30]}...")

            if url and self.downloader.download_file(url, file_path):
                # 分类存储
                self.classifier.classify_and_save(report, file_path)
                print(f"  保存成功: {file_path}")
            else:
                print(f"  下载失败或已存在")

        print("\n下载完成！检查 data/by_code/ 目录")


def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="A股上市公司财报爬虫")
    parser.add_argument("--test", action="store_true", help="测试模式")
    parser.add_argument("--test-count", type=int, default=10, help="测试模式下处理的股票数量")
    parser.add_argument("--test-stock", type=str, default="000001", help="测试单只股票")
    parser.add_argument("--mode", type=str, default="full", choices=["full", "test", "single"],
                        help="运行模式: full=全量, test=测试, single=单只股票")

    args = parser.parse_args()

    crawler = FinancialReportCrawler()

    if args.mode == "single" or args.test:
        stock_code = args.test_stock
        print(f"单股票测试模式: {stock_code}")
        crawler.test_single_stock(stock_code)
    elif args.mode == "test":
        print("多股票测试模式")
        crawler.crawl_all_stocks(test_mode=True, test_count=args.test_count)
    else:
        print("全量爬取模式")
        crawler.crawl_all_stocks(test_mode=False)


if __name__ == "__main__":
    main()
