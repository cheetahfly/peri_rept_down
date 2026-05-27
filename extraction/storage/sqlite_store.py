# -*- coding: utf-8 -*-
"""
SQLite存储模块
"""

import os
import json
import sqlite3
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

import pandas as pd

from extraction.config import EXTRACTION_DB_PATH, EXPORT_DIR

logger = logging.getLogger(__name__)


class SqliteStore:
    """SQLite格式存储"""

    def __init__(self, db_path: str = None):
        """
        初始化存储

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path or EXTRACTION_DB_PATH
        self._init_db()

    ENGINE_VERSION = "1.0"

    def _init_db(self):
        """初始化数据库表和迁移"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                report_year INTEGER NOT NULL,
                statement_type TEXT NOT NULL,
                data TEXT NOT NULL,
                confidence REAL,
                items_count INTEGER,
                engine_version TEXT,
                quality_flags TEXT,
                extraction_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stock_code, report_year, statement_type)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extraction_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                report_year INTEGER NOT NULL,
                statement_type TEXT NOT NULL,
                data TEXT NOT NULL,
                confidence REAL,
                items_count INTEGER,
                engine_version TEXT,
                quality_flags TEXT,
                extraction_id TEXT,
                archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extraction_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                extraction_id TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                report_year INTEGER NOT NULL,
                statement_type TEXT NOT NULL,
                item_name TEXT NOT NULL,
                item_value REAL
            )
        """)

        for idx in ["idx_stock_code", "idx_report_year", "idx_extraction_id", "idx_items_name"]:
            if idx == "idx_stock_code":
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_code ON extractions(stock_code)")
            elif idx == "idx_report_year":
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_report_year ON extractions(report_year)")
            elif idx == "idx_extraction_id":
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_extraction_id ON extraction_items(extraction_id)")
            elif idx == "idx_items_name":
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_name ON extraction_items(statement_type, item_name)")

        # 迁移：为已有 extractions 表添加新列（SQLite 不支持 IF NOT EXISTS for ALTER）
        existing_cols = {c[1] for c in cursor.execute("PRAGMA table_info(extractions)").fetchall()}
        for col_def in [
            ("confidence", "REAL"),
            ("items_count", "INTEGER"),
            ("engine_version", "TEXT"),
            ("quality_flags", "TEXT"),
            ("extraction_id", "TEXT"),
        ]:
            if col_def[0] not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE extractions ADD COLUMN {col_def[0]} {col_def[1]}")
                except Exception:
                    pass

        conn.commit()
        conn.close()

    def save(self, stock_code: str, year: int, statement_type: str,
             data: Dict, confidence: float = None, quality_flags: list = None,
             extraction_id: str = None) -> bool:
        """
        保存提取结果（含元数据和审计追踪）

        Args:
            stock_code: 股票代码
            year: 报告年份
            statement_type: 报表类型
            data: 提取的数据
            confidence: 提取置信度
            quality_flags: 质量门控标记
            extraction_id: 提取批次ID

        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 1. 存档旧记录
            cursor.execute("""
                SELECT data, confidence, items_count, engine_version, quality_flags, extraction_id
                FROM extractions
                WHERE stock_code = ? AND report_year = ? AND statement_type = ?
            """, (stock_code, year, statement_type))
            old = cursor.fetchone()
            if old:
                cursor.execute("""
                    INSERT INTO extraction_archive
                        (stock_code, report_year, statement_type, data,
                         confidence, items_count, engine_version, quality_flags, extraction_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (stock_code, year, statement_type) + old)

            # 2. 写入新记录
            data_json = json.dumps(data, ensure_ascii=False)
            flat = data.get("data", {}) if isinstance(data, dict) else {}
            items_count = len(flat)
            qflags_json = json.dumps(quality_flags or [], ensure_ascii=False)
            eid = extraction_id or f"{stock_code}_{year}_{statement_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            eid_stmt = f"{eid}_{statement_type}"

            cursor.execute("""
                INSERT OR REPLACE INTO extractions
                    (stock_code, report_year, statement_type, data,
                     confidence, items_count, engine_version, quality_flags, extraction_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stock_code, year, statement_type, data_json,
                  confidence, items_count, self.ENGINE_VERSION, qflags_json, eid_stmt,
                  datetime.now().isoformat()))

            # 3. 写入科目级数据（支持SQL查询）
            cursor.execute("""
                DELETE FROM extraction_items
                WHERE extraction_id = ? AND statement_type = ?
            """, (eid_stmt, statement_type))
            for item_name, item_value in flat.items():
                if isinstance(item_value, (int, float)):
                    cursor.execute("""
                        INSERT INTO extraction_items
                            (extraction_id, stock_code, report_year, statement_type, item_name, item_value)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (eid_stmt, stock_code, year, statement_type, item_name, item_value))

            conn.commit()
            return True

        except Exception as e:
            logger.warning(f"保存数据失败 ({stock_code}/{year}/{statement_type}): {e}")
            return False

        finally:
            conn.close()

    def save_all(self, stock_code: str, year: int, extracted_data: Dict) -> int:
        """
        保存所有报表类型（含置信度等元数据）

        Args:
            stock_code: 股票代码
            year: 报告年份
            extracted_data: {报表类型: 结果}, 结果中含 confidence/quality_flags

        Returns:
            保存成功数量
        """
        count = 0
        extraction_id = f"{stock_code}_{year}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        for statement_type, data in extracted_data.items():
            if not isinstance(data, dict) or not data.get("found"):
                continue
            if statement_type in ("ratios", "quality", "indicators"):
                continue

            confidence = data.get("confidence")
            quality = extracted_data.get("quality", {})
            qflags = quality.get("quality_flags") if quality.get("quality_flags") else None

            if self.save(stock_code, year, statement_type, data,
                         confidence=confidence, quality_flags=qflags,
                         extraction_id=extraction_id):
                count += 1

        return count

    def load(self, stock_code: str, year: int, statement_type: str) -> Optional[Dict]:
        """
        加载单条数据

        Args:
            stock_code: 股票代码
            year: 报告年份
            statement_type: 报表类型

        Returns:
            数据字典或None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT data FROM extractions
                WHERE stock_code = ? AND report_year = ? AND statement_type = ?
            """, (stock_code, year, statement_type))

            row = cursor.fetchone()
            if row:
                return json.loads(row[0])

            return None

        finally:
            conn.close()

    def load_all(self, stock_code: str = None, year: int = None) -> List[Dict]:
        """
        加载数据列表

        Args:
            stock_code: 股票代码（可选）
            year: 报告年份（可选）

        Returns:
            数据列表
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            query = "SELECT stock_code, report_year, statement_type, data, created_at FROM extractions"
            params = []

            conditions = []
            if stock_code:
                conditions.append("stock_code = ?")
                params.append(stock_code)
            if year:
                conditions.append("report_year = ?")
                params.append(year)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY stock_code, report_year DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
        finally:
            conn.close()

        results = []
        for row in rows:
            results.append({
                "stock_code": row[0],
                "report_year": row[1],
                "statement_type": row[2],
                "data": json.loads(row[3]),
                "created_at": row[4],
            })

        return results

    def list_stocks(self) -> List[Tuple[str, List[int]]]:
        """
        列出所有股票及其有数据的年份

        Returns:
            [(股票代码, [年份列表])]
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT stock_code, report_year
            FROM extractions
            ORDER BY stock_code, report_year DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        # 转换为 {股票代码: [年份]} 格式
        stock_years = {}
        for stock_code, year in rows:
            if stock_code not in stock_years:
                stock_years[stock_code] = []
            if year not in stock_years[stock_code]:
                stock_years[stock_code].append(year)

        return [(k, v) for k, v in sorted(stock_years.items())]

    def delete(self, stock_code: str, year: int, statement_type: str = None) -> int:
        """
        删除数据

        Args:
            stock_code: 股票代码
            year: 报告年份
            statement_type: 报表类型（可选，为None则删除所有类型）

        Returns:
            删除的行数
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if statement_type:
            cursor.execute("""
                DELETE FROM extractions
                WHERE stock_code = ? AND report_year = ? AND statement_type = ?
            """, (stock_code, year, statement_type))
        else:
            cursor.execute("""
                DELETE FROM extractions
                WHERE stock_code = ? AND report_year = ?
            """, (stock_code, year))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted

    def get_stats(self) -> Dict:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            stats = {}

            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM extractions")
            stats["total_records"] = cursor.fetchone()[0]

            # 股票数
            cursor.execute("SELECT COUNT(DISTINCT stock_code) FROM extractions")
            stats["total_stocks"] = cursor.fetchone()[0]

            # 年份范围
            cursor.execute("SELECT MIN(report_year), MAX(report_year) FROM extractions")
            row = cursor.fetchone()
            stats["year_range"] = (row[0], row[1]) if row[0] else (None, None)

            # 各类型报表数
            cursor.execute("""
                SELECT statement_type, COUNT(*) FROM extractions GROUP BY statement_type
            """)
            stats["by_type"] = {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            conn.close()

        return stats

    def get_multi_year_data(
        self,
        stock_code: str,
        statement_type: str,
        years: List[int],
    ) -> Dict[int, Dict[str, float]]:
        """
        获取单股票多年数据用于对比分析

        Args:
            stock_code: 股票代码
            statement_type: 报表类型
            years: 年份列表

        Returns:
            {年份: {科目名: 值}}
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            query = """
                SELECT report_year, data
                FROM extractions
                WHERE stock_code = ? AND statement_type = ? AND report_year IN ({})
                ORDER BY report_year
            """.format(','.join('?' * len(years)))

            cursor.execute(query, [stock_code, statement_type] + years)
            rows = cursor.fetchall()
        finally:
            conn.close()

        result = {}
        for year, data_json in rows:
            data = json.loads(data_json)
            result[year] = data.get("data", {})

        return result

    def get_multi_stock_data(
        self,
        stock_codes: List[str],
        year: int,
        statement_type: str,
    ) -> Dict[Tuple[str, str], Dict[str, float]]:
        """
        获取多股票同年数据

        Args:
            stock_codes: 股票代码列表
            year: 报告年份
            statement_type: 报表类型

        Returns:
            {(股票代码, 股票名称): {科目名: 值}}
        """
        if not stock_codes:
            return {}

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            placeholders = ','.join('?' * len(stock_codes))
            query = f"""
                SELECT stock_code, data
                FROM extractions
                WHERE stock_code IN ({placeholders}) AND report_year = ? AND statement_type = ?
            """

            cursor.execute(query, stock_codes + [year, statement_type])
            rows = cursor.fetchall()
        finally:
            conn.close()

        result = {}
        for stock_code, data_json in rows:
            data = json.loads(data_json)
            result[(stock_code, stock_code)] = data.get("data", {})

        return result

    def export_table(
        self,
        df: pd.DataFrame,
        file_path: str = None,
        format: str = 'csv',
    ) -> str:
        """
        导出DataFrame为CSV或Excel

        Args:
            df: 要导出的DataFrame
            file_path: 文件路径（可选）
            format: 格式 ('csv' 或 'excel')

        Returns:
            保存的文件路径
        """
        if file_path is None:
            os.makedirs(EXPORT_DIR, exist_ok=True)
            file_path = os.path.join(EXPORT_DIR, f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}")

        os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else ".", exist_ok=True)

        if format == 'csv':
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
        elif format == 'excel':
            df.to_excel(file_path, index=False, engine='openpyxl')

        return file_path
