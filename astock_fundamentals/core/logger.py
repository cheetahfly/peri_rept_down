# -*- coding: utf-8 -*-
"""
统一日志系统

功能:
- 结构化JSON日志输出
- 错误分类统计
- 多级别日志 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- 日志文件轮转
- 性能日志

用法:
    from logger import get_logger, LogContext, ErrorTracker
    
    logger = get_logger("extraction")
    logger.info("开始提取", extra={"stock_code": "000001", "year": 2024})
    
    with LogContext(logger, "extract_balance_sheet"):
        # 操作
        pass
    
    # 错误统计
    tracker = ErrorTracker()
    tracker.record_error("PDF_NOT_FOUND", "data/by_code/000001/test.pdf")
    tracker.report()
"""

import os
import sys
import json
import time
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict
from functools import wraps
from contextlib import contextmanager


class LogLevel(Enum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class ErrorCategory(Enum):
    """错误分类"""
    # PDF处理错误
    PDF_NOT_FOUND = "PDF_NOT_FOUND"
    PDF_READ_ERROR = "PDF_READ_ERROR"
    PDF_PARSE_ERROR = "PDF_PARSE_ERROR"
    PDF_ENCRYPTED = "PDF_ENCRYPTED"
    PDF_CORRUPT = "PDF_CORRUPT"
    
    # 表格提取错误
    TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
    TABLE_PARSE_ERROR = "TABLE_PARSE_ERROR"
    TABLE_STRUCTURE_ERROR = "TABLE_STRUCTURE_ERROR"
    
    # OCR错误
    OCR_NOT_AVAILABLE = "OCR_NOT_AVAILABLE"
    OCR_ERROR = "OCR_ERROR"
    OCR_LOW_CONFIDENCE = "OCR_LOW_CONFIDENCE"
    
    # 网络错误
    NETWORK_ERROR = "NETWORK_ERROR"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_RATE_LIMIT = "NETWORK_RATE_LIMIT"
    
    # 数据错误
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_ERROR"
    DATA_MISSING_FIELD = "DATA_MISSING_FIELD"
    DATA_TYPE_ERROR = "DATA_TYPE_ERROR"
    
    # 提取质量错误
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    BALANCE_CHECK_FAILED = "BALANCE_CHECK_FAILED"
    EXTRACTION_INCOMPLETE = "EXTRACTION_INCOMPLETE"
    
    # 未知错误
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass
class LogRecord:
    """日志记录"""
    timestamp: str
    level: str
    logger: str
    message: str
    error_category: Optional[str] = None
    error_details: Optional[str] = None
    duration_ms: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None


class StructuredLogger:
    """结构化日志记录器"""
    
    _instances: Dict[str, 'StructuredLogger'] = {}
    _default_level = LogLevel.INFO
    
    def __init__(self, name: str, log_file: Optional[str] = None):
        self.name = name
        self.log_file = log_file
        self._error_counts: Dict[str, int] = {}
        self._error_records: list = []
    
    @classmethod
    def get_instance(cls, name: str, log_file: Optional[str] = None) -> 'StructuredLogger':
        if name not in cls._instances:
            cls._instances[name] = cls(name, log_file)
        return cls._instances[name]
    
    def _write(self, record: LogRecord):
        """写入日志"""
        log_line = json.dumps(asdict(record), ensure_ascii=False)
        
        # 输出到控制台
        print(log_line)
        
        # 输出到文件
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(log_line + '\n')
            except Exception as e:
                print(f"日志写入失败: {e}", file=sys.stderr)
    
    def _make_record(
        self,
        level: LogLevel,
        message: str,
        error_category: Optional[ErrorCategory] = None,
        error_details: Optional[str] = None,
        duration_ms: Optional[float] = None,
        stack_trace: bool = False,
        **extra
    ) -> LogRecord:
        """创建日志记录"""
        record = LogRecord(
            timestamp=datetime.now().isoformat(),
            level=level.name,
            logger=self.name,
            message=message,
            error_category=error_category.value if error_category else None,
            error_details=error_details,
            duration_ms=duration_ms,
            extra=extra,
            stack_trace=traceback.format_stack() if stack_trace else None
        )
        
        # 记录错误
        if error_category:
            self._error_counts[error_category.value] = self._error_counts.get(error_category.value, 0) + 1
            self._error_records.append({
                "category": error_category.value,
                "message": message,
                "details": error_details,
                "timestamp": record.timestamp
            })
        
        return record
    
    def debug(self, message: str, **extra):
        if self._default_level.value <= LogLevel.DEBUG.value:
            self._write(self._make_record(LogLevel.DEBUG, message, **extra))
    
    def info(self, message: str, **extra):
        if self._default_level.value <= LogLevel.INFO.value:
            self._write(self._make_record(LogLevel.INFO, message, **extra))
    
    def warning(self, message: str, **extra):
        if self._default_level.value <= LogLevel.WARNING.value:
            self._write(self._make_record(LogLevel.WARNING, message, **extra))
    
    def error(
        self,
        message: str,
        error_category: Optional[ErrorCategory] = None,
        error_details: Optional[str] = None,
        stack_trace: bool = False,
        **extra
    ):
        if self._default_level.value <= LogLevel.ERROR.value:
            self._write(self._make_record(
                LogLevel.ERROR, message,
                error_category=error_category,
                error_details=error_details,
                stack_trace=stack_trace,
                **extra
            ))
    
    def critical(
        self,
        message: str,
        error_category: Optional[ErrorCategory] = None,
        error_details: Optional[str] = None,
        stack_trace: bool = True,
        **extra
    ):
        self._write(self._make_record(
            LogLevel.CRITICAL, message,
            error_category=error_category,
            error_details=error_details,
            stack_trace=stack_trace,
            **extra
        ))
    
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误统计摘要"""
        total_errors = sum(self._error_counts.values())
        return {
            "logger": self.name,
            "total_errors": total_errors,
            "error_counts": self._error_counts.copy(),
            "recent_errors": self._error_records[-10:]  # 最近10个错误
        }


class ErrorTracker:
    """错误追踪器 - 跨模块错误统计"""
    
    _instance: Optional['ErrorTracker'] = None
    
    def __init__(self):
        self.errors: list = []
        self.counts: Dict[str, int] = {}
    
    @classmethod
    def get_instance(cls) -> 'ErrorTracker':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def record_error(
        self,
        category: str,
        message: str,
        details: Optional[str] = None,
        context: Optional[Dict] = None
    ):
        """记录错误"""
        self.errors.append({
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "message": message,
            "details": details,
            "context": context or {}
        })
        self.counts[category] = self.counts.get(category, 0) + 1
    
    def report(self) -> Dict[str, Any]:
        """生成错误报告"""
        return {
            "total_errors": len(self.errors),
            "counts_by_category": self.counts.copy(),
            "recent_10": self.errors[-10:],
            "oldest_10": self.errors[:10] if len(self.errors) > 10 else []
        }
    
    def reset(self):
        """重置错误记录"""
        self.errors.clear()
        self.counts.clear()


@contextmanager
def LogContext(logger: StructuredLogger, operation: str, **context):
    """日志上下文管理器 - 自动记录操作耗时和异常"""
    start_time = time.time()
    logger.info(f"[START] {operation}", operation=operation, **context)
    
    try:
        yield
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"[END] {operation} 完成", operation=operation, duration_ms=duration_ms, **context)
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[ERROR] {operation} 失败",
            error_category=ErrorCategory.UNKNOWN_ERROR,
            error_details=str(e),
            duration_ms=duration_ms,
            operation=operation,
            **context
        )
        raise


def log_function_call(logger: StructuredLogger):
    """函数调用日志装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with LogContext(logger, func.__name__):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# 全局日志获取函数
_loggers: Dict[str, StructuredLogger] = {}
_default_log_dir = os.path.join(os.path.dirname(__file__), "logs")

def get_logger(
    name: str,
    log_file: Optional[str] = None,
    level: LogLevel = LogLevel.INFO
) -> StructuredLogger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称 (如模块名)
        log_file: 日志文件路径 (可选)
        level: 日志级别
    
    Returns:
        StructuredLogger 实例
    """
    global _loggers, _default_level
    
    if name in _loggers:
        return _loggers[name]
    
    # 确定日志文件
    if log_file is None:
        log_file = os.path.join(_default_log_dir, f"{name}.log")
    
    # 确保日志目录存在
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    logger = StructuredLogger.get_instance(name, log_file)
    logger._default_level = level
    _loggers[name] = logger
    
    return logger


# 便捷函数
def log_extraction_start(stock_code: str, year: int, pdf_path: str):
    """记录提取开始"""
    logger = get_logger("extraction")
    logger.info(
        "开始提取财务数据",
        stock_code=stock_code,
        year=year,
        pdf_path=pdf_path
    )

def log_extraction_end(stock_code: str, year: int, duration_ms: float, items_extracted: int):
    """记录提取结束"""
    logger = get_logger("extraction")
    logger.info(
        "提取完成",
        stock_code=stock_code,
        year=year,
        duration_ms=duration_ms,
        items_extracted=items_extracted
    )

def log_extraction_error(stock_code: str, year: int, error: Exception, context: Dict = None):
    """记录提取错误"""
    logger = get_logger("extraction")
    
    # 分类错误
    error_msg = str(error)
    if "not found" in error_msg.lower() or "不存在" in error_msg:
        category = ErrorCategory.PDF_NOT_FOUND
    elif "permission" in error_msg.lower() or "权限" in error_msg:
        category = ErrorCategory.PDF_READ_ERROR
    elif "corrupt" in error_msg.lower() or "损坏" in error_msg:
        category = ErrorCategory.PDF_CORRUPT
    else:
        category = ErrorCategory.UNKNOWN_ERROR
    
    logger.error(
        "提取失败",
        error_category=category,
        error_details=error_msg,
        stock_code=stock_code,
        year=year,
        context=context or {}
    )

def log_crawl_start(stock_code: str, url: str):
    """记录爬取开始"""
    logger = get_logger("crawler")
    logger.info("开始爬取", stock_code=stock_code, url=url)

def log_crawl_error(stock_code: str, error: Exception):
    """记录爬取错误"""
    logger = get_logger("crawler")
    error_msg = str(error)
    
    if "timeout" in error_msg.lower():
        category = ErrorCategory.NETWORK_TIMEOUT
    elif "rate limit" in error_msg.lower() or "频繁" in error_msg:
        category = ErrorCategory.NETWORK_RATE_LIMIT
    else:
        category = ErrorCategory.NETWORK_ERROR
    
    logger.error(
        "爬取失败",
        error_category=category,
        error_details=error_msg,
        stock_code=stock_code
    )


if __name__ == "__main__":
    # 测试日志系统
    logger = get_logger("test")
    
    logger.info("测试信息日志")
    logger.warning("测试警告日志")
    logger.error(
        "测试错误日志",
        error_category=ErrorCategory.PDF_NOT_FOUND,
        error_details="文件不存在: test.pdf",
        stock_code="000001"
    )
    
    with LogContext(logger, "test_operation"):
        time.sleep(0.1)
        pass
    
    tracker = ErrorTracker.get_instance()
    tracker.record_error("PDF_NOT_FOUND", "test.pdf")
    print(json.dumps(tracker.report(), indent=2, ensure_ascii=False))
