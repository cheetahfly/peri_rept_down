# -*- coding: utf-8 -*-
"""
获取上市公司财报列表
"""

import requests
import time
import random
from typing import List, Dict, Optional
from config import CNINFO_BASE_URL, HEADERS, REQUEST_DELAY, USER_AGENTS, REPORT_CATEGORIES


class ReportListCrawler:
    """爬取上市公司财报列表"""

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

            except Exception as e:
                print(f"请求异常: {e}")
                if attempt < retries - 1:
                    time.sleep(REQUEST_DELAY * (attempt + 1))

        return None

    def search_reports(
        self,
        stock_code: str = "",
        category: str = "annual",
        page: int = 1,
        page_size: int = 100
    ) -> Optional[Dict]:
        """
        使用搜索接口获取财报列表

        Args:
            stock_code: 股票代码
            category: 财报类型 (annual/half_year/quarter)
            page: 页码
            page_size: 每页数量

        Returns:
            包含财报列表的字典
        """
        url = f"{CNINFO_BASE_URL}/new/fulltextSearch/full"

        # 确定搜索关键词 - 使用股票代码+报告类型组合搜索
        category_info = REPORT_CATEGORIES.get(category, REPORT_CATEGORIES["annual"])
        search_key = category_info["name"]  # "年报", "半年报", "季报"

        # 如果指定了股票代码，加上股票代码作为搜索前缀
        if stock_code:
            search_key = stock_code + " " + search_key

        data = {
            "searchkey": search_key,
            "sdate": "",
            "edate": "",
            "isfulltext": "false",
            "sortName": "nothing",
            "sortType": "desc",
            "pageNum": page,
            "pageSize": page_size,
        }

        return self._make_request(url, data)

    def get_reports_by_category(
        self,
        org_id: str,
        stock_code: str,
        category: str = "annual",
        page: int = 1,
        page_size: int = 100
    ) -> Optional[Dict]:
        """
        获取指定分类的财报列表

        Args:
            org_id: 组织ID
            stock_code: 股票代码
            category: 财报类型 (annual/half_year/quarter)
            page: 页码
            page_size: 每页数量

        Returns:
            包含财报列表的字典
        """
        return self.search_reports(stock_code=stock_code, category=category, page=page, page_size=page_size)

    def get_all_reports(self, org_id: str, stock_code: str, stock_name: str) -> List[Dict]:
        """
        获取某公司所有类型的财报列表

        Args:
            org_id: 组织ID
            stock_code: 股票代码
            stock_name: 公司名称

        Returns:
            财报列表
        """
        all_reports = []

        for category, info in REPORT_CATEGORIES.items():
            print(f"  获取 {info['name']} 列表...")

            page = 1
            page_size = 100
            total_pages = 1

            while page <= total_pages:
                result = self.get_reports_by_category(
                    org_id=org_id,
                    stock_code=stock_code,
                    category=category,
                    page=page,
                    page_size=page_size
                )

                if result and not result.get("error_msg"):
                    announcements = result.get("announcements") or []
                    total_count = result.get("totalRecordNum", 0)
                    total_pages = (total_count + page_size - 1) // page_size if total_count > page_size else 1

                    for ann in announcements:
                        report = self._parse_announcement(ann, category, info["name"], stock_code, stock_name)
                        all_reports.append(report)

                    print(f"    第 {page}/{max(total_pages, 1)} 页，获取 {len(announcements)} 条")

                    if not announcements or page >= total_pages:
                        break

                    page += 1
                    time.sleep(REQUEST_DELAY)
                else:
                    print(f"    获取失败")
                    break

        return all_reports

    def _parse_announcement(self, ann: Dict, category: str, category_name: str, stock_code: str, stock_name: str) -> Dict:
        """
        解析公告为财报记录

        Args:
            ann: 原始公告数据
            category: 财报类型
            category_name: 财报类型名称
            stock_code: 股票代码
            stock_name: 公司名称

        Returns:
            解析后的财报信息
        """
        import re
        title = ann.get("announcementTitle", "")

        # 去除HTML标签
        clean_title = re.sub(r'<[^>]+>', '', title)

        # 提取年份 - 优先查找报告类型附近的4位数字
        year = None
        # 匹配年报、半年报、季报前的年份
        patterns = [
            r'(\d{4})\s*年\s*(?:半|一|三|四|[一二三四五六七八九十]+)?[年上报]',
            r'(\d{4})\s*年',
            r'(\d{4})',
        ]
        for pattern in patterns:
            match = re.search(pattern, clean_title)
            if match:
                potential_year = int(match.group(1))
                if 1990 <= potential_year <= 2100:
                    year = potential_year
                    break

        # 如果解析失败，尝试从announcementTime获取
        if year is None:
            announcement_time = ann.get("announcementTime")
            if announcement_time:
                import datetime
                year = datetime.datetime.fromtimestamp(announcement_time / 1000).year

        return {
            "announcement_id": ann.get("announcementId"),
            "stock_code": stock_code,
            "stock_name": stock_name,
            "category": category,
            "category_name": category_name,
            "report_year": year,
            "announcement_title": title,
            "announcement_url": ann.get("adjunctUrl"),
            "announcement_date": self._format_timestamp(ann.get("announcementTime")),
            "org_id": ann.get("orgId"),
        }

    def _format_timestamp(self, timestamp: int) -> str:
        """将时间戳转换为日期字符串"""
        if not timestamp:
            return ""
        import datetime
        return datetime.datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")

    def parse_report_info(self, report: Dict) -> Dict:
        """
        解析财报信息

        Args:
            report: 原始财报数据

        Returns:
            解析后的财报信息
        """
        return report


def test():
    """测试函数 - 以平安银行为例"""
    crawler = ReportListCrawler()
    org_id = "gssz0000001"
    reports = crawler.get_all_reports(org_id, "000001", "平安银行")
    print(f"获取到 {len(reports)} 条财报记录")


if __name__ == "__main__":
    test()
