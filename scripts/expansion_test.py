# -*- coding: utf-8 -*-
"""
扩展测试脚本 - 从深交所、上交所、北交所各选3家公司测试
"""

import sys
import os
import time
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CNINFO_BASE_URL, HEADERS, REQUEST_DELAY, USER_AGENTS
from crawlers.report_list import ReportListCrawler
from crawlers.downloader import ReportDownloader
from storage.classifier import generate_file_name
from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor


class ExpansionTester:
    """扩展测试类"""

    EXCHANGE_RANGES = {
        "SZSE": {  # 深圳证券交易所
            "name": "深圳证券交易所",
            "prefixes": ["000", "001", "002", "003", "300"],
            "description": "主板(000/001)、中小板(002)、创业板(300)",
        },
        "SSE": {  # 上海证券交易所
            "name": "上海证券交易所",
            "prefixes": ["600", "601", "603", "688"],
            "description": "主板(600/601)、科创板(688)",
        },
        "BSE": {  # 北京证券交易所
            "name": "北京证券交易所",
            "prefixes": ["430", "830", "870", "889"],  # 北交所股票代码
            "description": "北交所",
        },
    }

    def __init__(self):
        self.report_crawler = ReportListCrawler()
        self.downloader = ReportDownloader()
        self.session = self.report_crawler.session

    def _get_random_ua(self):
        return random.choice(USER_AGENTS)

    def _make_request(self, url, data=None, retries=3):
        for attempt in range(retries):
            try:
                headers = self.session.headers.copy()
                headers["User-Agent"] = self._get_random_ua()
                if data:
                    response = self.session.post(
                        url, data=data, headers=headers, timeout=30
                    )
                else:
                    response = self.session.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 403:
                    print(f"请求被禁止 (403)，等待 {REQUEST_DELAY * 2} 秒...")
                    time.sleep(REQUEST_DELAY * 2)
            except Exception as e:
                print(f"请求异常: {e}")
                if attempt < retries - 1:
                    time.sleep(REQUEST_DELAY * (attempt + 1))
        return None

    def get_stocks_by_exchange(self, exchange_code):
        """获取指定交易所的股票列表"""
        exchange = self.EXCHANGE_RANGES.get(exchange_code, {})
        prefixes = exchange.get("prefixes", [])

        url = f"{CNINFO_BASE_URL}/new/fulltextSearch/full"
        all_stocks = []
        seen_codes = set()

        # 搜索上市公司
        for prefix in prefixes:
            for page in range(1, 5):
                search_key = f"{prefix} 公司"
                data = {
                    "searchkey": search_key,
                    "sdate": "",
                    "edate": "",
                    "isfulltext": "false",
                    "sortName": "nothing",
                    "sortType": "desc",
                    "pageNum": page,
                    "pageSize": 100,
                }

                result = self._make_request(url, data)
                if not result or result.get("error_msg"):
                    break

                announcements = result.get("announcements", [])
                if not announcements:
                    break

                for ann in announcements:
                    code = ann.get("secCode", "")
                    name = ann.get("secName", "")
                    org_id = ann.get("orgId", "")
                    if code and code not in seen_codes and code.startswith(prefix):
                        seen_codes.add(code)
                        all_stocks.append(
                            {
                                "stockCode": code,
                                "securityName": name,
                                "orgId": org_id,
                            }
                        )

                time.sleep(REQUEST_DELAY)

                if len(all_stocks) >= 50:
                    break

            if len(all_stocks) >= 50:
                break

        return all_stocks[:50]

    def get_annual_reports(self, stock_code, stock_name, org_id):
        """获取某股票的年报列表"""
        url = f"{CNINFO_BASE_URL}/new/fulltextSearch/full"
        search_key = f"{stock_code} 年报"
        data = {
            "searchkey": search_key,
            "sdate": "",
            "edate": "",
            "isfulltext": "false",
            "sortName": "nothing",
            "sortType": "desc",
            "pageNum": 1,
            "pageSize": 20,
        }

        result = self._make_request(url, data)
        reports = []

        if result and not result.get("error_msg"):
            announcements = result.get("announcements", [])
            for ann in announcements:
                title = ann.get("announcementTitle", "")
                if "年报" in title and "摘要" not in title:
                    reports.append(
                        {
                            "announcement_id": ann.get("announcementId"),
                            "stock_code": stock_code,
                            "stock_name": stock_name,
                            "category": "annual",
                            "category_name": "年报",
                            "announcement_title": title,
                            "announcement_url": ann.get("adjunctUrl"),
                            "announcement_date": "",
                            "org_id": org_id,
                        }
                    )

        return reports

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
            return None

        return results

    def run_expansion_test(self):
        """运行扩展测试"""
        print("=" * 70)
        print("扩展测试 - 深交所/上交所/北交所各3家公司")
        print("=" * 70)

        all_results = {}
        failed_stocks = []

        for exchange_code, exchange_info in self.EXCHANGE_RANGES.items():
            print(f"\n{'=' * 70}")
            print(f"交易所: {exchange_info['name']} ({exchange_code})")
            print(f"说明: {exchange_info['description']}")
            print(f"{'=' * 70}")

            # 获取股票列表
            print(f"获取股票列表...")
            stocks = self.get_stocks_by_exchange(exchange_code)
            print(f"获取到 {len(stocks)} 只股票")

            if not stocks:
                print(f"未能获取 {exchange_code} 的股票")
                continue

            # 选择3只股票
            selected = stocks[:3]
            print(f"选择测试: {[s['stockCode'] for s in selected]}")

            for i, stock in enumerate(selected):
                stock_code = stock["stockCode"]
                stock_name = stock["securityName"]
                org_id = stock["orgId"]

                print(f"\n[{i + 1}/3] {stock_code} {stock_name}")

                # 获取年报
                reports = self.get_annual_reports(stock_code, stock_name, org_id)
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

                # 下载第一份年报
                report = reports[0]
                title = report.get("announcement_title", "")[:40]
                print(f"  年报: {title}")

                save_dir = os.path.join("data", "by_code", stock_code)
                file_path, success = self.download_report(report, save_dir)

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
                print(f"  测试提取...")
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

        for exchange_code in self.EXCHANGE_RANGES.keys():
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
    tester = ExpansionTester()
    tester.run_expansion_test()
