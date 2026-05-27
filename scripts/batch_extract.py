# -*- coding: utf-8 -*-
"""
批量提取脚本 - 对下载的PDF执行数据提取与质量检查

扫描 data/by_code/ 下所有PDF，执行提取，生成汇总报告。
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from multiprocessing import Pool, cpu_count
from glob import glob

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BY_CODE_DIR, CATEGORY_NAME_TO_TYPE
from extraction.cli import extract_single_pdf, parse_pdf_path
from extraction.storage.sqlite_store import SqliteStore


def _extract_worker(args: tuple) -> dict:
    """multiprocessing worker"""
    pdf_path, output_dir = args
    try:
        return extract_single_pdf(pdf_path, output_dir, save_json=True, save_db=True)
    except Exception as e:
        return {"success": False, "error": str(e), "pdf_path": pdf_path}


def scan_pdfs(pdf_dir: str) -> list:
    """扫描所有PDF文件"""
    pdfs = []
    for root, _, files in os.walk(pdf_dir):
        for f in files:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    return sorted(pdfs)


def batch_extract(pdf_dir: str = None, output_dir: str = None,
                  workers: int = 4, pattern: str = None) -> dict:
    """
    批量提取所有PDF

    Args:
        pdf_dir: PDF目录（默认 data/by_code）
        output_dir: 输出目录
        workers: 并行worker数
        pattern: 文件匹配模式（未使用，保留接口）

    Returns:
        汇总结果
    """
    pdf_dir = pdf_dir or BY_CODE_DIR
    workers = min(workers, cpu_count())

    # 扫描PDF
    pdfs = scan_pdfs(pdf_dir)
    if not pdfs:
        print(f"未找到PDF文件: {pdf_dir}")
        return {"total": 0, "success": 0, "failed": 0}

    print(f"找到 {len(pdfs)} 个PDF文件")
    print(f"使用 {workers} 个worker并行处理")

    # 构建任务列表
    tasks = [(pdf_path, output_dir) for pdf_path in pdfs]

    # 并行执行
    results = []
    start_time = time.time()

    with Pool(workers) as pool:
        for i, result in enumerate(pool.imap_unordered(_extract_worker, tasks)):
            results.append(result)
            # 进度显示
            if (i + 1) % 10 == 0 or (i + 1) == len(tasks):
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(tasks) - i - 1) / rate if rate > 0 else 0
                print(f"  进度: {i + 1}/{len(tasks)} "
                      f"({(i + 1) / len(tasks) * 100:.0f}%) "
                      f"速度: {rate:.1f}/s ETA: {eta:.0f}s")

    elapsed = time.time() - start_time

    # 统计
    success = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"\n{'=' * 60}")
    print("提取完成")
    print(f"{'=' * 60}")
    print(f"总耗时: {elapsed:.0f}s ({elapsed / len(pdfs):.1f}s/PDF)")
    print(f"成功: {len(success)}/{len(results)}")
    print(f"失败: {len(failed)}/{len(results)}")

    # 按股票/年份/类型分组统计
    stats = {}
    for r in success:
        code = r.get("stock_code", "?")
        year = r.get("year", "?")
        rtype = r.get("report_type", "annual")
        key = f"{code}_{year}_{rtype}"
        if key not in stats:
            stats[key] = {"bs": 0, "is": 0, "cf": 0}
        results_data = r.get("results", {})
        if results_data.get("balance_sheet", {}).get("found"):
            stats[key]["bs"] = len(results_data["balance_sheet"].get("data", {}))
        if results_data.get("income_statement", {}).get("found"):
            stats[key]["is"] = len(results_data["income_statement"].get("data", {}))
        if results_data.get("cash_flow", {}).get("found"):
            stats[key]["cf"] = len(results_data["cash_flow"].get("data", {}))

    if stats:
        print(f"\n{'─' * 60}")
        print(f"{'股票_年份_类型':<30} {'BS':>4} {'IS':>4} {'CF':>4}")
        print(f"{'─' * 60}")
        for key in sorted(stats.keys()):
            s = stats[key]
            print(f"{key:<30} {s['bs']:>4} {s['is']:>4} {s['cf']:>4}")

    # 失败详情
    if failed:
        print(f"\n{'─' * 60}")
        print("失败详情:")
        for r in failed[:10]:
            pdf = r.get("pdf_path", "?")
            err = r.get("error", "?")
            print(f"  {pdf}: {err[:80]}")

    # 保存汇总报告
    report = {
        "generated_at": datetime.now().isoformat(),
        "pdf_dir": pdf_dir,
        "total_pdfs": len(pdfs),
        "success": len(success),
        "failed": len(failed),
        "elapsed_seconds": round(elapsed, 1),
        "per_pdf_seconds": round(elapsed / len(pdfs), 1) if pdfs else 0,
        "details": stats,
    }
    report_path = os.path.join(pdf_dir, "..", "extraction_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n汇总报告: {os.path.abspath(report_path)}")

    return report


def main():
    parser = argparse.ArgumentParser(description="批量提取A股财报PDF数据")
    parser.add_argument("--input", type=str, default=None,
                        help="PDF目录 (默认: data/by_code)")
    parser.add_argument("--output", type=str, default=None,
                        help="输出目录")
    parser.add_argument("--workers", type=int, default=4,
                        help="并行worker数")
    parser.add_argument("--stock-codes", type=str, default="",
                        help="只处理指定股票代码，逗号分隔")

    args = parser.parse_args()

    pdf_dir = args.input or BY_CODE_DIR

    # 如果指定了股票代码，只处理这些目录
    if args.stock_codes:
        codes = [c.strip() for c in args.stock_codes.split(",")]
        # 创建临时目录结构，只包含指定股票的PDF
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="extract_")
        for code in codes:
            src = os.path.join(pdf_dir, code)
            if os.path.isdir(src):
                dst = os.path.join(tmp_dir, code)
                os.symlink(src, dst)
        pdf_dir = tmp_dir

    batch_extract(
        pdf_dir=pdf_dir,
        output_dir=args.output,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
