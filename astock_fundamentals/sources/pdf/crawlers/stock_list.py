# -*- coding: utf-8 -*-
"""
获取A股上市公司列表
"""

import requests
import time
import random
from typing import List, Dict, Optional
from config import CNINFO_BASE_URL, HEADERS, REQUEST_DELAY, USER_AGENTS


class StockListCrawler:
    """爬取A股上市公司列表"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get_random_ua(self) -> str:
        """随机获取User-Agent"""
        return random.choice(USER_AGENTS)

    def _make_request(self, url: str, data: Dict = None, retries: int = 3) -> Optional[Dict]:
        """发送请求，带重试机制"""
        for attempt in range(retries):
            try:
                headers = self.session.headers.copy()
                headers["User-Agent"] = self._get_random_ua()

                if data:
                    response = self.session.post(url, data=data, headers=headers, timeout=30)
                else:
                    response = self.session.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 403:
                    print(f"请求被禁止 (403)，等待 {REQUEST_DELAY * 2} 秒后重试...")
                    time.sleep(REQUEST_DELAY * 2)
                else:
                    print(f"请求失败: {response.status_code}")

            except requests.exceptions.RequestException as e:
                print(f"请求异常: {e}")
                if attempt < retries - 1:
                    time.sleep(REQUEST_DELAY * (attempt + 1))

        return None

    def get_stock_list(self, page: int = 1, page_size: int = 100) -> Optional[Dict]:
        """
        获取股票列表

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            包含股票列表的字典
        """
        url = f"{CNINFO_BASE_URL}/new/fulltextSearch/full"

        # 搜索所有A股上市公司
        search_keyword = "上市"  # 这个接口是全文搜索，需要调整策略

        data = {
            "searchkey": search_keyword,
            "sdate": "",
            "edate": "",
            "isfulltext": "false",
            "sortName": "nothing",
            "sortType": "desc",
            "pageNum": page,
            "pageSize": page_size,
        }

        return self._make_request(url, data)

    def get_all_stocks(self) -> List[Dict]:
        """
        获取所有A股上市公司列表

        Returns:
            股票列表，每项包含 orgId, stockCode, companyName 等
        """
        all_stocks = []
        page = 1
        page_size = 500
        total_pages = 1

        print("开始获取股票列表...")

        while page <= total_pages:
            result = self.get_stock_list(page=page, page_size=page_size)

            if result and not result.get("error_msg"):
                stocks = result.get("announcements", [])
                total_count = result.get("totalRecordNum", 0)
                total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

                if page == 1:
                    print(f"共找到 {total_count} 家上市公司，分为 {total_pages} 页")

                # 标准化字段名: secCode -> stockCode, secName -> securityName
                normalized_stocks = []
                for s in stocks:
                    normalized_stocks.append({
                        "stockCode": s.get("secCode"),
                        "securityName": s.get("secName"),
                        "orgId": s.get("orgId"),
                    })

                all_stocks.extend(normalized_stocks)
                print(f"第 {page}/{total_pages} 页，获取 {len(stocks)} 条记录")

                # 检查是否已获取足够的股票
                if not stocks:
                    break

                page += 1
                time.sleep(REQUEST_DELAY)
            else:
                error_msg = result.get("error_msg", "未知错误") if result else "无响应"
                print(f"获取失败: {error_msg}")
                break

        print(f"共获取 {len(all_stocks)} 家公司的信息")
        return all_stocks

    def get_stock_info(self, org_id: str) -> Optional[Dict]:
        """
        获取单个股票的详细信息

        Args:
            org_id: 组织ID

        Returns:
            股票信息字典
        """
        url = f"{CNINFO_BASE_URL}/new/disclosure/stock"
        params = {"orgId": org_id, "stockCode": ""}

        try:
            headers = self.session.headers.copy()
            headers["User-Agent"] = self._get_random_ua()

            response = self.session.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.json()

        except requests.exceptions.RequestException as e:
            print(f"获取股票信息失败: {e}")

        return None


def test():
    """测试函数"""
    crawler = StockListCrawler()
    stocks = crawler.get_stock_list(page=1, page_size=10)
    print(stocks)


if __name__ == "__main__":
    test()
