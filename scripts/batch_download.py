# -*- coding: utf-8 -*-
"""
批量下载脚本 - 下载A股上市公司财报PDF

支持：
- 指定股票数量/代码/行业
- 指定年份范围（2022-2025）
- 指定报告类型（年报、半年报、季报）
- 断点续传
- PDF验证
"""

import os
import sys
import json
import time
import random
import argparse
import re
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    REQUEST_DELAY, REPORT_CATEGORIES, TARGET_YEARS, CATEGORY_NAME_TO_TYPE,
    BY_CODE_DIR,
)
from stock_universe import STOCK_UNIVERSE, get_all_codes
from crawlers.report_list import ReportListCrawler
from crawlers.downloader import ReportDownloader
from crawlers.pdf_verifier import PdfVerifier


# ── 断点续传 ──────────────────────────────────────────────

CHECKPOINT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "download_checkpoint.json")
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "download_manifest.json")


class Checkpoint:
    """断点续传管理"""

    def __init__(self, path: str = CHECKPOINT_PATH):
        self.path = path
        self.done = set()
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.done = set(tuple(x) for x in data.get("done", []))

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"done": [list(x) for x in self.done]}, f, ensure_ascii=False)

    def is_done(self, stock_code: str, year: int, report_type: str) -> bool:
        return (stock_code, str(year), report_type) in self.done

    def mark_done(self, stock_code: str, year: int, report_type: str):
        self.done.add((stock_code, str(year), report_type))
        self.save()


class Manifest:
    """下载清单管理"""

    def __init__(self, path: str = MANIFEST_PATH):
        self.path = path
        self.records = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.records = data.get("results", [])

    def add(self, record: dict):
        self.records.append(record)
        self.save()

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        summary = {
            "generated_at": datetime.now().isoformat(),
            "total_records": len(self.records),
            "success": sum(1 for r in self.records if r.get("status") == "success"),
            "rejected": sum(1 for r in self.records if r.get("status") == "rejected"),
            "failed": sum(1 for r in self.records if r.get("status") == "failed"),
            "results": self.records,
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)


# ── 标题过滤 ──────────────────────────────────────────────

def is_valid_report_title(title: str, year: int) -> bool:
    """检查标题是否为有效的正式财报（排除摘要、英文版、公告等）"""
    if "摘要" in title:
        return False
    if "英文" in title:
        return False
    if any(kw in title for kw in ["说明会", "通知", "提示", "工作规程", "制度", "预案"]):
        return False
    return True


def match_year_from_title(title: str, announce_time: int, target_year: int) -> bool:
    """检查公告是否属于目标年份"""
    # 标题中包含年份
    if str(target_year) in title:
        return True
    # 从发布时间判断
    if announce_time:
        pub_year = datetime.fromtimestamp(announce_time / 1000).year
        # 年报：目标年份发布（次年1-4月）
        # 半年报：目标年份发布（同年7-9月）
        # 季报：目标年份发布
        if pub_year == target_year or pub_year == target_year + 1:
            return True
    return False


# ── 核心下载逻辑 ──────────────────────────────────────────

def download_stock_reports(
    stock_code: str,
    stock_name: str,
    years: list,
    report_types: list,
    verifier: PdfVerifier,
    manifest: Manifest,
    checkpoint: Checkpoint,
):
    """下载单只股票的所有报告"""
    rc = ReportListCrawler()
    dl = ReportDownloader()
    results = []

    for year in years:
        for report_type in report_types:
            if checkpoint.is_done(stock_code, year, report_type):
                continue

            # 确定CNINFO搜索类别（季报统一用"quarter"搜索）
            search_category = "quarter" if report_type.startswith("quarter") else report_type
            category_info = REPORT_CATEGORIES.get(search_category, REPORT_CATEGORIES["annual"])

            # 搜索
            search_result = rc.search_reports(
                stock_code=stock_code,
                category=search_category,
                page=1,
                page_size=100,
            )

            if not search_result:
                checkpoint.mark_done(stock_code, year, report_type)
                time.sleep(REQUEST_DELAY)
                continue

            announcements = search_result.get("announcements", [])

            # 过滤
            target_ann = None
            for ann in announcements:
                title = ann.get("announcementTitle", "")
                clean_title = re.sub(r'<[^>]+>', '', title)

                # 检查是否属于目标年份
                if not match_year_from_title(clean_title, ann.get("announcementTime", 0), year):
                    continue

                # 检查报告子类型（Q1/Q3）
                if report_type == "quarter_q1":
                    if not any(kw in clean_title for kw in ["第一季度", "一季报", "第一季"]):
                        continue
                elif report_type == "quarter_q3":
                    if not any(kw in clean_title for kw in ["第三季度", "三季报", "第三季", "三季"]):
                        continue

                # 排除摘要等无效文档
                if not is_valid_report_title(clean_title, year):
                    continue

                adjunct_url = ann.get("adjunctUrl", "")
                if adjunct_url:
                    target_ann = (clean_title, adjunct_url, ann.get("announcementTime", 0))
                    break

            if not target_ann:
                checkpoint.mark_done(stock_code, year, report_type)
                time.sleep(REQUEST_DELAY)
                continue

            clean_title, adjunct_url, ann_time = target_ann

            # 构建保存路径
            category_name = CATEGORY_NAME_TO_TYPE.get(report_type, report_type)
            # 反向查找中文名
            for cn_name, internal in CATEGORY_NAME_TO_TYPE.items():
                if internal == report_type:
                    category_name = cn_name
                    break
            safe_name = stock_name.replace("*", "_").replace("/", "_").replace("\\", "_")
            fname = f"{stock_code}_{safe_name}_{year}_{category_name}.PDF"
            target_dir = os.path.join(BY_CODE_DIR, stock_code)
            os.makedirs(target_dir, exist_ok=True)
            save_path = os.path.join(target_dir, fname)

            # 跳过已存在
            if os.path.exists(save_path):
                checkpoint.mark_done(stock_code, year, report_type)
                results.append({
                    "stock_code": stock_code, "stock_name": stock_name,
                    "year": year, "report_type": report_type,
                    "status": "exists", "file_path": save_path,
                })
                continue

            # 下载
            success = dl.download_file(adjunct_url, save_path)
            if not success:
                manifest.add({
                    "stock_code": stock_code, "stock_name": stock_name,
                    "year": year, "report_type": report_type,
                    "status": "failed", "reason": "下载失败",
                })
                checkpoint.mark_done(stock_code, year, report_type)
                time.sleep(REQUEST_DELAY)
                continue

            # PDF验证
            verification = verifier.verify(save_path, report_type)
            if not verification["valid"]:
                rejected_path = save_path + ".rejected"
                os.rename(save_path, rejected_path)
                manifest.add({
                    "stock_code": stock_code, "stock_name": stock_name,
                    "year": year, "report_type": report_type,
                    "status": "rejected", "reason": verification["reason"],
                    "file_path": rejected_path,
                })
                print(f"    X 验证失败: {verification['reason']}")
            else:
                fsize = os.path.getsize(save_path) / (1024 * 1024)
                manifest.add({
                    "stock_code": stock_code, "stock_name": stock_name,
                    "year": year, "report_type": report_type,
                    "status": "success", "file_path": save_path,
                    "file_size_mb": round(fsize, 1),
                    "title": clean_title,
                })
                print(f"    OK 下载成功: {fname} ({fsize:.1f}MB)")

            checkpoint.mark_done(stock_code, year, report_type)
            results.append({
                "stock_code": stock_code, "stock_name": stock_name,
                "year": year, "report_type": report_type,
                "status": "success" if verification["valid"] else "rejected",
            })

            time.sleep(REQUEST_DELAY + random.uniform(0, 1))

    return results


# ── 主入口 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="批量下载A股财报PDF")
    parser.add_argument("--stocks", type=int, default=0,
                        help="从股票池中取前N只股票 (0=全部)")
    parser.add_argument("--stock-codes", type=str, default="",
                        help="指定股票代码，逗号分隔 (如: 000001,600036)")
    parser.add_argument("--industries", type=str, default="",
                        help="按行业筛选，逗号分隔 (如: 银行,白酒)")
    parser.add_argument("--years", type=str, default="2022-2025",
                        help="年份范围 (如: 2022-2025 或 2025)")
    parser.add_argument("--types", type=str, default="annual,half_year,quarter",
                        help="报告类型，逗号分隔 (annual,half_year,quarter)")
    parser.add_argument("--resume", action="store_true", help="断点续传")
    parser.add_argument("--verify-only", action="store_true", help="仅验证已下载的PDF")

    args = parser.parse_args()

    # 解析年份范围
    if "-" in args.years:
        start, end = args.years.split("-")
        years = list(range(int(start), int(end) + 1))
    else:
        years = [int(args.years)]

    # 解析报告类型
    report_types = [t.strip() for t in args.types.split(",")]

    # 选择股票
    if args.stock_codes:
        codes = [c.strip() for c in args.stock_codes.split(",")]
        stocks = []
        for code in codes:
            found = next((s for s in STOCK_UNIVERSE if s["code"] == code), None)
            if found:
                stocks.append(found)
            else:
                stocks.append({"code": code, "name": code, "industry": "未知", "exchange": "未知"})
    elif args.industries:
        industries = [i.strip() for i in args.industries.split(",")]
        stocks = [s for s in STOCK_UNIVERSE if s["industry"] in industries]
    elif args.stocks > 0:
        stocks = STOCK_UNIVERSE[:args.stocks]
    else:
        stocks = STOCK_UNIVERSE

    print("=" * 60)
    print("A股财报PDF批量下载")
    print("=" * 60)
    print(f"股票数: {len(stocks)}")
    print(f"年份: {years}")
    print(f"报告类型: {report_types}")
    print(f"预计最大下载量: {len(stocks) * len(years) * len(report_types)}")
    print()

    # 仅验证模式
    if args.verify_only:
        verifier = PdfVerifier()
        print("PDF验证模式")
        for stock in stocks:
            stock_dir = os.path.join(BY_CODE_DIR, stock["code"])
            if not os.path.isdir(stock_dir):
                continue
            for fname in os.listdir(stock_dir):
                if not fname.lower().endswith(".pdf"):
                    continue
                fpath = os.path.join(stock_dir, fname)
                # 推断报告类型
                report_type = "annual"
                for cn_name, internal in CATEGORY_NAME_TO_TYPE.items():
                    if cn_name in fname:
                        report_type = internal
                        break
                v = verifier.verify(fpath, report_type)
                status = "OK" if v["valid"] else "X"
                print(f"  {status} {stock['code']}/{fname}: {v['reason'] or 'OK'}")
        return

    # 下载模式
    verifier = PdfVerifier()
    checkpoint = Checkpoint() if args.resume else Checkpoint()
    manifest = Manifest()

    if not args.resume:
        # 清空断点（非续传模式）
        checkpoint.done = set()

    total_success = 0
    total_failed = 0

    for i, stock in enumerate(stocks):
        print(f"\n[{i + 1}/{len(stocks)}] {stock['code']} {stock['name']} ({stock['industry']})")

        results = download_stock_reports(
            stock_code=stock["code"],
            stock_name=stock["name"],
            years=years,
            report_types=report_types,
            verifier=verifier,
            manifest=manifest,
            checkpoint=checkpoint,
        )

        success = sum(1 for r in results if r.get("status") == "success")
        exists = sum(1 for r in results if r.get("status") == "exists")
        total_success += success
        total_failed += len(results) - success - exists
        print(f"  结果: {success} 新下载, {exists} 已存在")

    print(f"\n{'=' * 60}")
    print("下载完成")
    print(f"{'=' * 60}")
    print(f"成功: {total_success}")
    print(f"已存在: {sum(1 for r in manifest.records if r.get('status') == 'exists')}")
    print(f"失败: {total_failed}")
    print(f"拒绝: {sum(1 for r in manifest.records if r.get('status') == 'rejected')}")
    print(f"清单: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
