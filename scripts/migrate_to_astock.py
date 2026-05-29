#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将现有代码迁移到 astock_fundamentals 包结构。
复制文件并重写 imports，不修改原始文件。
"""
import os, sys, shutil, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = BASE
DST = os.path.join(BASE, "astock_fundamentals")

# 文件映射: (源路径, 目标路径相对于DST)
FILE_MAP = [
    # ===== PDF parsers =====
    ("extraction/parsers/pdf_parser.py", "sources/pdf/parsers/pdf_parser.py"),
    ("extraction/parsers/table_parser.py", "sources/pdf/parsers/table_parser.py"),
    ("extraction/parsers/table_engine.py", "sources/pdf/parsers/table_engine.py"),
    ("extraction/parsers/hybrid_parser.py", "sources/pdf/parsers/hybrid_parser.py"),
    ("extraction/parsers/html_converter.py", "sources/pdf/parsers/html_converter.py"),
    ("extraction/parsers/html_parser.py", "sources/pdf/parsers/html_parser.py"),
    ("extraction/parsers/lo_table_parser.py", "sources/pdf/parsers/lo_table_parser.py"),
    ("extraction/parsers/ocr_parser.py", "sources/pdf/parsers/ocr_parser.py"),
    ("extraction/parsers/pymupdf_parser.py", "sources/pdf/parsers/pymupdf_parser.py"),
    ("extraction/parsers/windows_ocr.py", "sources/pdf/parsers/windows_ocr.py"),

    # ===== PDF extractors =====
    ("extraction/extractors/base.py", "sources/pdf/extractors/base.py"),
    ("extraction/extractors/income_statement.py", "sources/pdf/extractors/income_statement.py"),
    ("extraction/extractors/balance_sheet.py", "sources/pdf/extractors/balance_sheet.py"),
    ("extraction/extractors/cash_flow.py", "sources/pdf/extractors/cash_flow.py"),
    ("extraction/extractors/indicators.py", "sources/pdf/extractors/indicators.py"),

    # ===== Crawlers =====
    ("crawlers/downloader.py", "sources/pdf/crawlers/downloader.py"),
    ("crawlers/report_list.py", "sources/pdf/crawlers/report_list.py"),
    ("crawlers/stock_list.py", "sources/pdf/crawlers/stock_list.py"),
    ("crawlers/pdf_verifier.py", "sources/pdf/crawlers/pdf_verifier.py"),

    # ===== RDS =====
    ("extraction/ground_truth/rds_loader.py", "sources/rds/rds_loader.py"),

    # ===== Ground truth =====
    ("extraction/ground_truth/comparator.py", "ground_truth/comparator.py"),
    ("extraction/ground_truth/gap_analyzer.py", "ground_truth/gap_analyzer.py"),
    ("extraction/ground_truth/mapper.py", "ground_truth/mapper.py"),
    ("extraction/ground_truth/auto_learner.py", "ground_truth/auto_learner.py"),
    ("extraction/ground_truth/rule_applier.py", "ground_truth/rule_applier.py"),

    # ===== Core utilities =====
    ("logger.py", "core/logger.py"),
    ("monitoring.py", "core/monitoring.py"),
    ("performance.py", "core/performance.py"),
    ("stock_universe.py", "core/stock_universe.py"),

    # ===== Storage =====
    ("extraction/storage/json_store.py", "core/storage/json_store.py"),
    ("extraction/storage/sqlite_store.py", "core/storage/sqlite_store.py"),

    # ===== Quality =====
    ("extraction/quality_gate.py", "core/quality_gate.py"),
    ("extraction/quality_report.py", "core/quality_report.py"),
    ("extraction/cid_detector.py", "core/cid_detector.py"),
    ("extraction/semantic_recovery.py", "core/semantic_recovery.py"),
    ("extraction/word_recovery.py", "core/word_recovery.py"),
    ("extraction/label_recovery.py", "core/label_recovery.py"),
    ("extraction/cas_mapper.py", "core/cas_mapper.py"),
    ("extraction/cas_vocabulary.py", "core/cas_vocabulary.py"),
    ("extraction/table_formatter.py", "core/table_formatter.py"),

    # ===== Reports =====
    ("reports/daily_report.py", "reports/daily_report.py"),

    # ===== Main =====
    ("main.py", "core/main.py"),
]

# Import rewrite rules
IMPORT_REPLACEMENTS = [
    # 通用 extraction 替换
    (r'from extraction\.parsers\.', 'from astock_fundamentals.sources.pdf.parsers.'),
    (r'import extraction\.parsers\.', 'import astock_fundamentals.sources.pdf.parsers.'),
    (r'from extraction\.extractors\.', 'from astock_fundamentals.sources.pdf.extractors.'),
    (r'import extraction\.extractors\.', 'import astock_fundamentals.sources.pdf.extractors.'),
    (r'from extraction\.ground_truth\.', 'from astock_fundamentals.ground_truth.'),
    (r'import extraction\.ground_truth\.', 'import astock_fundamentals.ground_truth.'),
    (r'from extraction\.storage\.', 'from astock_fundamentals.core.storage.'),
    (r'import extraction\.storage\.', 'import astock_fundamentals.core.storage.'),
    (r'from extraction\.exporters\.', 'from astock_fundamentals.core.exporters.'),
    (r'from extraction\.config', 'from astock_fundamentals.core.extraction_config'),
    (r'import extraction\.config', 'import astock_fundamentals.core.extraction_config'),
    (r'from extraction\.', 'from astock_fundamentals.core.'),
    (r'import extraction\.', 'import astock_fundamentals.'),
    # Crawlers
    (r'from crawlers\.', 'from astock_fundamentals.sources.pdf.crawlers.'),
    (r'import crawlers\.', 'import astock_fundamentals.sources.pdf.crawlers.'),
    # Root modules
    (r'^from config import', 'from astock_fundamentals.core.config import'),
    (r'^import config', 'import astock_fundamentals.core.config'),
    (r'^from logger import', 'from astock_fundamentals.core.logger import'),
    (r'^import logger', 'import astock_fundamentals.core.logger'),
    (r'^from monitoring import', 'from astock_fundamentals.core.monitoring import'),
    (r'^from performance import', 'from astock_fundamentals.core.performance import'),
    (r'^from stock_universe import', 'from astock_fundamentals.core.stock_universe import'),
]


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def copy_and_rewrite(src_rel, dst_rel):
    src_path = os.path.join(SRC, src_rel)
    dst_path = os.path.join(DST, dst_rel)
    if not os.path.exists(src_path):
        print(f"  SKIP (not found): {src_rel}")
        return
    ensure_dir(os.path.dirname(dst_path))

    with open(src_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Rewrite imports
    for pattern, replacement in IMPORT_REPLACEMENTS:
        content = re.sub(pattern, replacement, content)

    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  OK: {src_rel} -> {dst_rel}")


def main():
    print(f"Migrating from {SRC} to {DST}")
    print(f"\nCopying {len(FILE_MAP)} files...")
    for src_rel, dst_rel in FILE_MAP:
        copy_and_rewrite(src_rel, dst_rel)

    # Create __init__.py for exporters (doesn't exist in original but needed)
    exporters_dir = os.path.join(DST, "core", "exporters")
    ensure_dir(exporters_dir)
    init_path = os.path.join(exporters_dir, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, 'w', encoding='utf-8') as f:
            f.write("from .base import BaseExporter\nfrom .csv_exporter import CsvExporter\nfrom .excel_exporter import ExcelExporter\n")
        print(f"  OK: created core/exporters/__init__.py")

    # Also need to copy the exporter files if they exist
    for fname in ["base.py", "csv_exporter.py", "excel_exporter.py"]:
        src = os.path.join("extraction", "exporters", fname)
        dst = os.path.join("core", "exporters", fname)
        if os.path.exists(os.path.join(SRC, src)):
            copy_and_rewrite(src, dst)

    total = sum(1 for _, dst_rel in FILE_MAP if os.path.exists(os.path.join(DST, dst_rel)))
    print(f"\nDone. {total} files migrated.")
    print(f"Package located at: {DST}")


if __name__ == "__main__":
    main()
