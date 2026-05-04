# -*- coding: utf-8 -*-
"""
命令行工具 - 财报PDF数据提取
"""

import os
import sys
import re
import argparse
from glob import glob
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Pool, cpu_count

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor
from extraction.extractors.indicators import FinancialIndicatorsExtractor, RatioCalculator
from extraction.storage.json_store import JsonStore
from extraction.storage.sqlite_store import SqliteStore
from extraction.config import EXTRACTED_BY_CODE_DIR, EXPORT_DIR
from extraction.table_formatter import MultiPeriodTableBuilder, export_to_csv
from extraction.exporters import CsvExporter
from config import BY_CODE_DIR


# multiprocessing wrapper function (must be at module level for pickling)
def _extract_pdf_worker(args: tuple) -> Dict:
    """multiprocessing worker function for PDF extraction"""
    pdf_path, output_dir = args
    return extract_single_pdf(pdf_path, output_dir)


def _is_safe_path(path: str) -> bool:
    """
    Check if a path is safe from traversal attacks.

    A path is unsafe if it contains .. traversal sequences that could escape
    the intended directory, or if it resolves to an absolute path outside
    the project directory.
    """
    if ".." in path:
        return False
    abs_path = os.path.abspath(path)
    # Prevent absolute paths to system directories
    if abs_path.startswith("/etc") or abs_path.startswith("/root") or abs_path.startswith("C:\\Windows"):
        return False
    return True


def _validate_path_arg(path: str, arg_name: str, is_file: bool = True) -> None:
    """Validate a path argument; exit with error if unsafe."""
    if not _is_safe_path(path):
        print(f"错误: {arg_name} 包含非法路径序列")
        sys.exit(1)
    if is_file:
        if not os.path.isfile(path):
            print(f"错误: {arg_name} 不是有效文件: {path}")
            sys.exit(1)
    else:
        if not os.path.isdir(path):
            print(f"错误: {arg_name} 不是有效目录: {path}")
            sys.exit(1)


_STOCK_CODE_RE = re.compile(r"^\d{6}$")


def _validate_stock_code(stock_code: str, arg_name: str = "stock_code") -> None:
    """Validate stock code format (6 digits); exit with error if invalid."""
    if not _STOCK_CODE_RE.match(stock_code):
        print(f"错误: {arg_name} 格式无效（应为6位数字）: {stock_code}")
        sys.exit(1)


def parse_pdf_path(pdf_path: str) -> tuple:
    """
    从PDF路径解析股票代码和年份

    Args:
        pdf_path: PDF文件路径

    Returns:
        (股票代码, 年份) 或 (None, None)
    """
    filename = os.path.basename(pdf_path)

    # 匹配 000001_平安银行_2024_年报.pdf 格式
    match = re.match(r'^(\d{6})_.+?_(\d{4})_', filename)
    if match:
        return match.group(1), int(match.group(2))

    # 尝试其他格式
    stock_match = re.search(r'^(\d{6})', filename)
    year_match = re.search(r'(20\d{2})', filename)

    stock_code = stock_match.group(1) if stock_match else None
    year = int(year_match.group(1)) if year_match else None

    return stock_code, year


def deduplicate_pages(all_pages: Dict[str, List[int]], parser: 'PdfParser') -> Dict[str, List[int]]:
    """
    去重重叠页面，确保每个页面只属于一个提取器

    优先级裁决：页数少的提取器优先（内容更专业），页数多的提取器放弃重叠页

    Args:
        all_pages: {提取器名: [页码列表]}
        parser: PdfParser实例

    Returns:
        去重后的页面字典
    """
    # 建立页面 -> 归属映射
    page_to_extractors = {}  # page_num -> [extractor_names]
    for extractor_name, pages in all_pages.items():
        for p in pages:
            if p not in page_to_extractors:
                page_to_extractors[p] = []
            page_to_extractors[p].append(extractor_name)

    # 统计每个提取器的页数，页数少的优先（内容更专业）
    extractor_page_count = {name: len(pages) for name, pages in all_pages.items()}
    priority_order = sorted(extractor_page_count.keys(), key=lambda x: extractor_page_count[x])

    # 裁决：每个页面分配给优先级最高的提取器
    page_assignment = {}  # page_num -> extractor_name
    for page_num, extractors in page_to_extractors.items():
        for ext_name in priority_order:
            if ext_name in extractors:
                page_assignment[page_num] = ext_name
                break

    # 重新构建每个提取器的页面列表
    result = {name: [] for name in all_pages}
    for page_num, ext_name in page_assignment.items():
        result[ext_name].append(page_num)

    # 排序
    for name in result:
        result[name] = sorted(result[name])

    # 报告重叠解决情况
    overlaps = [p for p, exts in page_to_extractors.items() if len(exts) > 1]
    if overlaps:
        print(f"    页面重叠解决: {len(overlaps)} 个重叠页被裁决")
        for p in overlaps[:5]:
            print(f"      页{p} -> {page_assignment[p]} (候选: {page_to_extractors[p]})")

    return result


def extract_single_pdf(pdf_path: str, output_dir: str = None,
                       save_json: bool = True, save_db: bool = True) -> Dict:
    """
    提取单个PDF文件

    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        save_json: 是否保存JSON
        save_db: 是否保存到数据库

    Returns:
        提取结果
    """
    if not os.path.exists(pdf_path):
        return {"success": False, "error": f"文件不存在: {pdf_path}"}

    stock_code, year = parse_pdf_path(pdf_path)
    if not stock_code or not year:
        return {"success": False, "error": "无法解析股票代码和年份"}

    print(f"处理: {pdf_path}")
    print(f"  股票代码: {stock_code}, 年份: {year}")

    try:
        # 初始化PDF解析器
        with PdfParser(pdf_path) as parser:
            print(f"  PDF页数: {parser.page_count}")

            # 第一步：分别让各提取器找自己认定的页面
            candidate_pages = {}
            extractor_instances = {
                "balance_sheet": BalanceSheetExtractor(parser),
                "income_statement": IncomeStatementExtractor(parser),
                "cash_flow": CashFlowExtractor(parser),
            }
            for name, ext in extractor_instances.items():
                pages = ext._find_section_pages(parser)
                candidate_pages[name] = pages
                print(f"  {name} 初选页面: {pages}")

            # 第二步：去重裁决
            deduped_pages = deduplicate_pages(candidate_pages, parser)

            # 第三步：用裁决后的页面提取
            results = {}
            for stmt_type, extractor in extractor_instances.items():
                print(f"  提取 {stmt_type} (页面: {deduped_pages.get(stmt_type, [])})...")
                result = extractor.extract(discovered_pages=deduped_pages.get(stmt_type, []))
                results[stmt_type] = result

                if result.get("found"):
                    confidence = extractor.calculate_confidence(result)
                    print(f"    成功: {len(result.get('data', {}))} 条数据, 置信度: {confidence['overall']:.1%}")
                else:
                    print(f"    失败: {result.get('error', '未知错误')}")

            # 提取财务指标（复用已有parser实例，避免重复预热）
            print("  提取财务指标...")
            indicators_ext = FinancialIndicatorsExtractor(parser)
            indicators_result = indicators_ext.extract()
            results["indicators"] = indicators_result

            # 验证
            print("  验证数据...")
            balance_sheet_data = results.get("balance_sheet", {})
            income_data = results.get("income_statement", {})
            cash_flow_data = results.get("cash_flow", {})

            # 计算财务比率
            if balance_sheet_data.get("found") and income_data.get("found"):
                ratios = RatioCalculator.calculate_ratios(
                    balance_sheet_data.get("data", {}),
                    income_data.get("data", {}),
                    cash_flow_data.get("data", {})
                )
                results["ratios"] = ratios
                print(f"    计算了 {sum(len(v) for v in ratios.values())} 个财务比率")

            # 保存JSON
            if save_json:
                json_store = JsonStore(output_dir or EXTRACTED_BY_CODE_DIR)
                saved_files = json_store.save_all(stock_code, year, results)
                print(f"  保存JSON: {len(saved_files)} 个文件")

            # 保存数据库
            if save_db:
                db_store = SqliteStore()
                saved_count = db_store.save_all(stock_code, year, results)
                print(f"  保存数据库: {saved_count} 条记录")

            return {
                "success": True,
                "stock_code": stock_code,
                "year": year,
                "results": results
            }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "stock_code": stock_code,
            "year": year,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


def batch_extract(input_dir: str, output_dir: str = None,
                  workers: int = 4, pattern: str = "**/*.pdf") -> Dict:
    """
    批量提取PDF文件

    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        workers: 并行工作线程数
        pattern: 文件匹配模式

    Returns:
        处理统计
    """
    # 查找所有PDF文件
    search_path = os.path.join(input_dir, pattern)
    pdf_files = glob(search_path, recursive=True)

    if not pdf_files:
        print(f"未找到PDF文件: {search_path}")
        return {"total": 0, "success": 0, "failed": 0}

    print(f"找到 {len(pdf_files)} 个PDF文件")

    stats = {"total": len(pdf_files), "success": 0, "failed": 0}
    results = []

    # 使用 multiprocessing 替代 ThreadPoolExecutor 以绕过 GIL 限制
    # pdfplumber 的 CPU 密集型解析无法通过线程并行化
    actual_workers = min(workers, cpu_count(), len(pdf_files))
    print(f"启动 {actual_workers} 个进程并行处理 {len(pdf_files)} 个PDF文件")

    with Pool(processes=actual_workers) as pool:
        # imap_unordered 比 map 更好：已完成的任务立即返回，不等待其他任务
        # 使用 (pdf_path, output_dir) 元组作为参数
        work_items = [(p, output_dir) for p in pdf_files]
        for result in pool.imap_unordered(_extract_pdf_worker, work_items):
            if result.get("success"):
                stats["success"] += 1
            else:
                stats["failed"] += 1
                print(f"失败: {result.get('stock_code', 'unknown')} - {result.get('error', 'unknown error')}")
            results.append(result)

    return stats


def validate_extraction(json_path: str) -> Dict:
    """
    验证提取结果

    Args:
        json_path: JSON文件路径

    Returns:
        验证结果
    """
    if not os.path.exists(json_path):
        return {"valid": False, "error": "文件不存在"}

    import json
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"验证文件: {json_path}")
    print(f"股票代码: {data.get('stock_code')}")
    print(f"报告年份: {data.get('report_year')}")
    print(f"报表类型: {data.get('statement_type')}")

    stmt_data = data.get("data", {})
    print(f"数据条数: {len(stmt_data)}")

    # 检查关键字段
    issues = []

    if not stmt_data:
        issues.append("数据为空")

    # 检查合计项
    has_total = any("合计" in k or "总计" in k for k in stmt_data.keys())
    if not has_total:
        issues.append("缺少合计项")

    if issues:
        return {"valid": False, "issues": issues}
    else:
        return {"valid": True, "data": data}


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="A股财报PDF数据提取工具")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # extract子命令
    extract_parser = subparsers.add_parser("extract", help="提取单个PDF文件")
    extract_parser.add_argument("pdf_path", help="PDF文件路径")
    extract_parser.add_argument("-o", "--output", help="输出目录")

    # batch子命令
    batch_parser = subparsers.add_parser("batch", help="批量提取PDF文件")
    batch_parser.add_argument("input_dir", help="输入目录")
    batch_parser.add_argument("-o", "--output", help="输出目录")
    batch_parser.add_argument("-w", "--workers", type=int, default=4, help="并行工作数")
    batch_parser.add_argument("-p", "--pattern", default="**/*.pdf", help="文件匹配模式")

    # validate子命令
    validate_parser = subparsers.add_parser("validate", help="验证提取结果")
    validate_parser.add_argument("json_path", help="JSON文件路径")

    # list子命令
    list_parser = subparsers.add_parser("list", help="列出已提取的数据")
    list_parser.add_argument("-s", "--stock", help="股票代码")

    # export-table子命令
    export_parser = subparsers.add_parser("export-table", help="导出单股票多年对比表")
    export_parser.add_argument("-s", "--stock", required=True, help="股票代码")
    export_parser.add_argument("-y", "--years", required=True, help="年份列表，逗号分隔，如: 2024,2023,2022")
    export_parser.add_argument("-t", "--type", required=True,
                              choices=['balance_sheet', 'income_statement', 'cash_flow', 'indicators'],
                              help="报表类型")
    export_parser.add_argument("-f", "--format", default='csv', choices=['csv', 'excel', 'both'], help="导出格式")
    export_parser.add_argument("-o", "--output", help="输出文件路径")

    # batch-export子命令
    batch_export_parser = subparsers.add_parser("batch-export", help="批量导出多股票数据")
    batch_export_parser.add_argument("-i", "--input", required=True, help="股票代码列表文件路径")
    batch_export_parser.add_argument("-y", "--years", required=True, help="年份列表，逗号分隔")
    batch_export_parser.add_argument("-t", "--type", required=True,
                                     choices=['balance_sheet', 'income_statement', 'cash_flow', 'indicators'],
                                     help="报表类型")
    batch_export_parser.add_argument("-o", "--output", help="输出目录")

    report_parser = subparsers.add_parser("report", help="生成提取质量报告")
    report_parser.add_argument("-s", "--stock", required=True, help="股票代码")
    report_parser.add_argument("-y", "--year", help="报告年份")
    report_parser.add_argument("-d", "--pdf-dir", default="data/by_code", help="PDF文件目录")
    report_parser.add_argument("-o", "--output", default="data/reports", help="报告输出目录")
    report_parser.add_argument("--save", action="store_true", help="保存报告到文件")

    args = parser.parse_args()

    if args.command == "extract":
        _validate_path_arg(args.pdf_path, "pdf_path")
        result = extract_single_pdf(args.pdf_path, args.output)
        if result.get("success"):
            print(f"\n提取成功: {result['stock_code']} {result['year']}")
        else:
            print(f"\n提取失败: {result.get('error')}")
            sys.exit(1)

    elif args.command == "batch":
        _validate_path_arg(args.input_dir, "input_dir", is_file=False)
        stats = batch_extract(args.input_dir, args.output, args.workers, args.pattern)
        print(f"\n批量处理完成:")
        print(f"  总数: {stats['total']}")
        print(f"  成功: {stats['success']}")
        print(f"  失败: {stats['failed']}")

    elif args.command == "validate":
        _validate_path_arg(args.json_path, "json_path")
        result = validate_extraction(args.json_path)
        if result.get("valid"):
            print("\n验证通过")
        else:
            print(f"\n验证失败: {result.get('issues')}")
            sys.exit(1)

    elif args.command == "list":
        db = SqliteStore()
        stocks = db.list_stocks()
        if args.stock:
            stocks = [(code, years) for code, years in stocks if code == args.stock]

        if stocks:
            print(f"共 {len(stocks)} 只股票:")
            for code, years in stocks:
                print(f"  {code}: {years}")
        else:
            print("没有找到数据")

    elif args.command == "export-table":
        stock_code = args.stock
        _validate_stock_code(stock_code)
        years = [int(y.strip()) for y in args.years.split(',')]
        statement_type = args.type

        print(f"导出 {stock_code} 的 {statement_type} 表格")
        print(f"年份: {years}")

        # 从JSON加载数据
        json_store = JsonStore()
        kv_data_by_year = json_store.load_for_table(stock_code, years, statement_type)

        if not kv_data_by_year:
            print("未找到数据")
            sys.exit(1)

        print(f"找到 {len(kv_data_by_year)} 年的数据")

        # 构建表格
        builder = MultiPeriodTableBuilder()
        df = builder.build_single_stock(kv_data_by_year, statement_type, include_yoy=True)

        if df.empty:
            print("表格为空")
            sys.exit(1)

        # 导出
        output_path = args.output
        if not output_path:
            os.makedirs(EXPORT_DIR, exist_ok=True)
            output_path = os.path.join(EXPORT_DIR, f"{stock_code}_{statement_type}_{years[0]}_{years[-1]}_table.csv")

        exporter = CsvExporter()
        exporter.export(df, output_path)
        print(f"导出成功: {output_path}")

    elif args.command == "batch-export":
        input_file = args.input
        years = [int(y.strip()) for y in args.years.split(',')]
        statement_type = args.type

        # 读取股票代码列表
        _validate_path_arg(input_file, "input")

        with open(input_file, 'r', encoding='utf-8') as f:
            stock_codes = [line.strip() for line in f if line.strip()]

        if not stock_codes:
            print("股票代码列表为空")
            sys.exit(1)

        print(f"批量导出 {len(stock_codes)} 只股票的 {statement_type}")
        print(f"年份: {years}")

        output_dir = args.output or EXPORT_DIR
        os.makedirs(output_dir, exist_ok=True)

        json_store = JsonStore()
        builder = MultiPeriodTableBuilder()
        exporter = CsvExporter()

        success_count = 0
        for stock_code in stock_codes:
            if not _STOCK_CODE_RE.match(stock_code):
                print(f"跳过无效股票代码: {stock_code}")
                continue
            kv_data_by_year = json_store.load_for_table(stock_code, years, statement_type)
            if kv_data_by_year:
                df = builder.build_single_stock(kv_data_by_year, statement_type, include_yoy=True)
                if not df.empty:
                    output_path = os.path.join(output_dir, f"{stock_code}_{statement_type}_table.csv")
                    exporter.export(df, output_path)
                    success_count += 1

        print(f"导出完成: {success_count}/{len(stock_codes)} 成功")

    elif args.command == "report":
        _validate_stock_code(args.stock)
        report_command(args)

    else:
        parser.print_help()


def report_command(args):
    """生成提取质量报告"""
    from extraction.quality_report import generate_quality_report
    from extraction.parsers.pdf_parser import PdfParser
    from extraction.extractors.balance_sheet import BalanceSheetExtractor
    from extraction.extractors.income_statement import IncomeStatementExtractor
    from extraction.extractors.cash_flow import CashFlowExtractor
    from extraction.extractors.indicators import FinancialIndicatorsExtractor

    stock_code = args.stock
    year = int(args.year) if args.year else 2024

    pdf_files = list(Path(args.pdf_dir).glob(f"{stock_code}_*_{year}_*.pdf"))
    if not pdf_files:
        pdf_files = list(Path(args.pdf_dir).glob(f"{stock_code}_*.pdf"))
    if not pdf_files:
        print(f"未找到股票 {stock_code} {year} 年的PDF文件")
        return

    pdf_path = str(pdf_files[0])
    print(f"使用PDF: {pdf_path}")

    results = {}

    with PdfParser(pdf_path) as parser:
        extractors = {
            "balance_sheet": BalanceSheetExtractor(parser),
            "income_statement": IncomeStatementExtractor(parser),
            "cash_flow": CashFlowExtractor(parser),
        }

        for stmt_type, extractor in extractors.items():
            result = extractor.extract()
            confidence = extractor.calculate_confidence(result)
            results[stmt_type] = {
                "result": result,
                "confidence": confidence,
            }
            print(f"{stmt_type}: {confidence['overall']:.1%}")

    report = generate_quality_report(stock_code, year, results, args.output)
    print(f"\n{report.generate_report()}")

    if args.save:
        filepath = report.save_report(args.output)
        print(f"\n报告已保存: {filepath}")


if __name__ == "__main__":
    main()
