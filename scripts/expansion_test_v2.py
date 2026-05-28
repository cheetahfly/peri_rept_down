# -*- coding: utf-8 -*-
"""
扩展测试脚本 v2 - 使用已知股票代码从三个交易所各选3家测试
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import REQUEST_DELAY
from crawlers.report_list import ReportListCrawler
from crawlers.downloader import ReportDownloader
from storage.classifier import generate_file_name
from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor


# 已知股票列表 (org_id, stock_code, stock_name)
STOCKS_BY_EXCHANGE = {
    "SZSE": [  # 深圳证券交易所
        ("gssz0000001", "000001", "平安银行"),
        ("gssz0000002", "000002", "万科A"),
        ("gssz0000024", "000024", "华侨城A"),
    ],
    "SSE": [  # 上海证券交易所
        ("gssz0600000", "600000", "浦发银行"),
        ("gssz0600036", "600036", "招商银行"),
        ("gssz0601111", "600111", "北方稀土"),
    ],
    "BSE": [  # 北京证券交易所
        ("gssz84300101", "430001", "佳先股份"),
        ("gssz84300188", "430188", "希伯伦"),
        ("gssz84300204", "430204", "绿岸网络"),
    ],
}


class ExpansionTesterV2:
    """扩展测试类 v2"""

    def __init__(self):
        self.report_crawler = ReportListCrawler()
        self.downloader = ReportDownloader()

    def get_annual_reports(self, org_id, stock_code, stock_name):
        """获取某股票的年报列表"""
        # Use the existing method from ReportListCrawler
        reports = self.report_crawler.get_all_reports(org_id, stock_code, stock_name)

        # Filter to only annual reports (年报)
        annual_reports = [r for r in reports if r.get("category_name") == "年报"]
        return annual_reports

    def download_report(self, report, save_dir):
        """下载单个财报"""
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, generate_file_name(report))

        if os.path.exists(file_path):
            print(f"  文件已存在: {file_path}")
            return file_path, True

        url = report.get("announcement_url", "")
        if not url:
            return None, False

        if self.downloader.download_file(url, file_path):
            return file_path, True
        return None, False

    def test_extraction(self, pdf_path):
        """测试提取功能"""
        results = {}

        try:
            with PdfParser(pdf_path) as parser:
                # Balance Sheet
                ext_bs = BalanceSheetExtractor(parser)
                r_bs = ext_bs.extract()
                conf_bs = ext_bs.calculate_confidence(r_bs)
                results["BS"] = conf_bs["overall"]

                # Income Statement
                ext_is = IncomeStatementExtractor(parser)
                r_is = ext_is.extract()
                conf_is = ext_is.calculate_confidence(r_is)
                results["IS"] = conf_is["overall"]

                # Cash Flow
                ext_cf = CashFlowExtractor(parser)
                r_cf = ext_cf.extract()
                conf_cf = ext_cf.calculate_confidence(r_cf)
                results["CF"] = conf_cf["overall"]

        except Exception as e:
            print(f"  提取错误: {e}")
            import traceback

            traceback.print_exc()
            return None

        return results

    def run_expansion_test(self):
        """运行扩展测试"""
        print("=" * 70)
        print("扩展测试 v2 - 深交所/上交所/北交所各3家公司")
        print("=" * 70)

        all_results = {}
        failed_stocks = []

        for exchange_code, stocks in STOCKS_BY_EXCHANGE.items():
            print(f"\n{'=' * 70}")
            print(f"交易所: {exchange_code}")
            print(f"{'=' * 70}")

            for i, (org_id, stock_code, stock_name) in enumerate(stocks):
                print(f"\n[{i + 1}/3] {stock_code} {stock_name}")

                # 获取年报
                reports = self.get_annual_reports(org_id, stock_code, stock_name)
                if not reports:
                    print(f"  未找到年报")
                    failed_stocks.append(
                        {
                            "exchange": exchange_code,
                            "stock_code": stock_code,
                            "stock_name": stock_name,
                            "reason": "未找到年报",
                        }
                    )
                    continue

                # 打印可用的年报
                years = []
                for r in reports[:10]:
                    year = r.get("report_year", "unknown")
                    title = r.get("announcement_title", "")[:30]
                    years.append(str(year))
                    print(f"  {year}: {title}")

                # 选择最新的2024或2025年报
                target_report = None
                for r in reports:
                    year = r.get("report_year")
                    if year in [2024, 2025]:
                        target_report = r
                        print(f"  选择: {year}年报")
                        break

                if not target_report:
                    target_report = reports[0]
                    print(f"  选择最新: {target_report.get('report_year')}年报")

                # 下载
                save_dir = os.path.join("data", "by_code", stock_code)
                file_path, success = self.download_report(target_report, save_dir)

                if not success or not file_path or not os.path.exists(file_path):
                    print(f"  下载失败")
                    failed_stocks.append(
                        {
                            "exchange": exchange_code,
                            "stock_code": stock_code,
                            "stock_name": stock_name,
                            "reason": "下载失败",
                        }
                    )
                    continue

                # 测试提取
                print(f"  测试提取: {file_path}")
                results = self.test_extraction(file_path)

                if results:
                    bs = results.get("BS", 0) * 100
                    is_ = results.get("IS", 0) * 100
                    cf = results.get("CF", 0) * 100
                    print(f"    BS: {bs:.1f}%, IS: {is_:.1f}%, CF: {cf:.1f}%")

                    key = f"{stock_code}_{exchange_code}"
                    all_results[key] = {
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "exchange": exchange_code,
                        "results": results,
                    }
                else:
                    failed_stocks.append(
                        {
                            "exchange": exchange_code,
                            "stock_code": stock_code,
                            "stock_name": stock_name,
                            "reason": "提取失败",
                        }
                    )

                time.sleep(REQUEST_DELAY)

        # 打印总结
        print("\n" + "=" * 70)
        print("扩展测试结果汇总")
        print("=" * 70)

        for exchange_code in STOCKS_BY_EXCHANGE.keys():
            exchange_stocks = {
                k: v for k, v in all_results.items() if v["exchange"] == exchange_code
            }
            if not exchange_stocks:
                continue

            print(f"\n{exchange_code}:")
            for key, data in exchange_stocks.items():
                r = data["results"]
                bs = r.get("BS", 0) * 100
                is_ = r.get("IS", 0) * 100
                cf = r.get("CF", 0) * 100
                print(
                    f"  {data['stock_code']} {data['stock_name']}: BS={bs:.0f}% IS={is_:.0f}% CF={cf:.0f}%"
                )

        if failed_stocks:
            print(f"\n失败股票:")
            for f in failed_stocks:
                print(
                    f"  {f['exchange']} {f['stock_code']} {f['stock_name']}: {f['reason']}"
                )

        # 计算总体
        total = len(all_results)
        if total > 0:
            passed = sum(
                1
                for v in all_results.values()
                if all(x >= 1.0 for x in v["results"].values())
            )
            print(f"\n总计: {total} 只股票, {passed} 只全通过")
            print(f"成功率: {passed / total * 100:.1f}%")

        return all_results


if __name__ == "__main__":
    tester = ExpansionTesterV2()
    tester.run_expansion_test()
