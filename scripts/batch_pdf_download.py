#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量下载 PDF 财报 - 针对有 Sina 数据的股票

下载策略：
1. 优先下载年报（数据最完整）
2. 然后半报告、季报
3. 断点续传支持
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import REQUEST_DELAY, REPORT_CATEGORIES, CATEGORY_NAME_TO_TYPE, BY_CODE_DIR
from crawlers.report_list import ReportListCrawler
from crawlers.downloader import ReportDownloader
from crawlers.pdf_verifier import PdfVerifier


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "akshare_bulk")
CHECKPOINT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pdf_download_checkpoint.json")


def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            return set(tuple(x) for x in json.load(f).get("done", []))
    return set()


def save_checkpoint(done):
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump({"done": [list(x) for x in done], "updated": datetime.now().isoformat()}, f)


def get_sina_complete_stocks():
    """获取有完整三大表 Sina 数据的股票"""
    progress_path = os.path.join(CACHE_DIR, "download_progress.json")
    if not os.path.exists(progress_path):
        return []

    with open(progress_path) as f:
        d = json.load(f)

    stock_stmts = {}
    for k, v in d.items():
        code = k.split("_")[0]
        st = k.split("_")[1]
        if v.get("status") == "done":
            if code not in stock_stmts:
                stock_stmts[code] = set()
            stock_stmts[code].add(st)

    # Only stocks with all 3 statements
    complete = [code for code, stmts in stock_stmts.items() if len(stmts) == 3]

    # Get names
    names = {}
    list_path = os.path.join(CACHE_DIR, "stock_list.csv")
    if os.path.exists(list_path):
        with open(list_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 2 and parts[0].isdigit():
                    names[parts[0]] = parts[1]

    return [(code, names.get(code, code)) for code in sorted(complete)]


def download_stock_annual(code, name, years, checkpoint):
    """下载单只股票的年报"""
    rc = ReportListCrawler()
    dl = ReportDownloader()
    verifier = PdfVerifier()
    results = []

    for year in years:
        key = (code, str(year), "annual")
        if key in checkpoint:
            continue

        # Search for annual report
        search_result = rc.search_reports(
            stock_code=code,
            category="annual",
            page=1,
            page_size=50,
        )

        if not search_result:
            checkpoint.add(key)
            time.sleep(REQUEST_DELAY)
            continue

        announcements = search_result.get("announcements", []) or []
        target_ann = None

        for ann in announcements:
            title = re.sub(r'<[^>]+>', '', ann.get("announcementTitle", ""))
            # Check if it's the annual report for target year
            if str(year) in title and "年报" in title:
                adjunct_url = ann.get("adjunctUrl", "")
                if adjunct_url:
                    target_ann = (title, adjunct_url)
                    break

        if not target_ann:
            checkpoint.add(key)
            time.sleep(REQUEST_DELAY)
            continue

        clean_title, adjunct_url = target_ann
        safe_name = name.replace("*", "_").replace("/", "_").replace("\\", "_")
        fname = f"{code}_{safe_name}_{year}_年报.pdf"
        target_dir = os.path.join(BY_CODE_DIR, code)
        os.makedirs(target_dir, exist_ok=True)
        save_path = os.path.join(target_dir, fname)

        if os.path.exists(save_path) or os.path.exists(save_path + ".rejected"):
            checkpoint.add(key)
            results.append({"code": code, "year": year, "status": "exists"})
            continue

        success = dl.download_file(adjunct_url, save_path)
        if success:
            verification = verifier.verify(save_path, "annual")
            if verification["valid"]:
                fsize = os.path.getsize(save_path) / (1024 * 1024)
                results.append({"code": code, "year": year, "status": "success", "size_mb": round(fsize, 1)})
                print(f"    OK {fname} ({fsize:.1f}MB)")
            else:
                os.rename(save_path, save_path + ".rejected")
                results.append({"code": code, "year": year, "status": "rejected", "reason": verification["reason"]})
                print(f"    X 验证失败: {verification['reason']}")
        else:
            results.append({"code": code, "year": year, "status": "failed"})

        checkpoint.add(key)
        time.sleep(REQUEST_DELAY + 0.5)

    return results


def main():
    parser = argparse.ArgumentParser(description="批量下载PDF财报")
    parser.add_argument("--stocks", type=int, default=50, help="下载前N只股票")
    parser.add_argument("--stock-codes", type=str, default="", help="指定股票代码，逗号分隔")
    parser.add_argument("--years", type=str, default="2020-2023", help="年份范围")
    parser.add_argument("--resume", action="store_true", help="断点续传")
    args = parser.parse_args()

    years = list(range(int(args.years.split("-")[0]), int(args.years.split("-")[1]) + 1))

    if args.stock_codes:
        codes = [c.strip() for c in args.stock_codes.split(",")]
        # Get names from stock list
        names = {}
        list_path = os.path.join(CACHE_DIR, "stock_list.csv")
        if os.path.exists(list_path):
            with open(list_path, encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) >= 2 and parts[0].isdigit():
                        names[parts[0]] = parts[1]
        stocks = [(c, names.get(c, c)) for c in codes]
    else:
        stocks = get_sina_complete_stocks()[:args.stocks]

    checkpoint = load_checkpoint() if args.resume else set()

    print("=" * 60)
    print(f"批量下载 PDF 财报")
    print(f"股票数: {len(stocks)}")
    print(f"年份: {years}")
    print(f"已完成: {len(checkpoint)} 个组合")
    print("=" * 60)

    total_success = 0
    total_failed = 0

    for i, (code, name) in enumerate(stocks):
        print(f"\n[{i+1}/{len(stocks)}] {code} {name}")
        results = download_stock_annual(code, name, years, checkpoint)
        success = sum(1 for r in results if r["status"] == "success")
        total_success += success
        print(f"  下载: {success}/{len(results)} 成功")

    print(f"\n{'='*60}")
    print(f"下载完成: {total_success} 个PDF")
    save_checkpoint(checkpoint)


if __name__ == "__main__":
    import re
    main()
