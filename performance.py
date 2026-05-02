# -*- coding: utf-8 -*-
"""
性能优化模块 - 并行下载和解析缓存
"""

import os
import hashlib
import json
import time
import shutil
from typing import List, Dict, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
PARSE_CACHE_DIR = os.path.join(CACHE_DIR, "parse_results")
DOWNLOAD_CACHE_DIR = os.path.join(CACHE_DIR, "download_status")


def ensure_cache_dir():
    """确保缓存目录存在"""
    os.makedirs(PARSE_CACHE_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_CACHE_DIR, exist_ok=True)


@dataclass
class DownloadTask:
    """下载任务"""
    stock_code: str
    year: int
    url: str
    file_path: str
    priority: int = 0  # 优先级，越高越先下载


@dataclass
class DownloadResult:
    """下载结果"""
    stock_code: str
    year: int
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class ParseCacheEntry:
    """解析缓存条目"""
    pdf_path: str
    pdf_hash: str  # 文件内容hash
    extracted_data: Dict[str, Any]
    confidence: float
    cached_at: str
    version: str = "1.0"  # 缓存版本，用于invalidating


class ParallelDownloader:
    """
    并行下载器
    
    使用ThreadPoolExecutor实现多线程并行下载
    支持优先级队列
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        retry_count: int = 3,
        retry_delay: float = 2.0
    ):
        """
        初始化并行下载器
        
        Args:
            max_workers: 最大并行数
            retry_count: 重试次数
            retry_delay: 重试延迟（秒）
        """
        self.max_workers = max_workers
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self._results: List[DownloadResult] = []
    
    def download_batch(
        self,
        tasks: List[DownloadTask],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[DownloadResult]:
        """
        批量并行下载
        
        Args:
            tasks: 下载任务列表
            progress_callback: 进度回调 (completed, total, message)
        
        Returns:
            下载结果列表
        """
        # 按优先级排序
        sorted_tasks = sorted(tasks, key=lambda t: -t.priority)
        total = len(sorted_tasks)
        completed = 0
        results = []
        
        # 导入下载器
        from crawlers.downloader import ReportDownloader
        
        def download_single(task: DownloadTask) -> DownloadResult:
            start_time = time.time()
            downloader = ReportDownloader()
            
            try:
                success = downloader.download_file(task.url, task.file_path)
                duration_ms = (time.time() - start_time) * 1000
                
                return DownloadResult(
                    stock_code=task.stock_code,
                    year=task.year,
                    success=success,
                    file_path=task.file_path if success else None,
                    error=None if success else "Download failed",
                    duration_ms=duration_ms
                )
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                return DownloadResult(
                    stock_code=task.stock_code,
                    year=task.year,
                    success=False,
                    error=str(e),
                    duration_ms=duration_ms
                )
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(download_single, task): task
                for task in sorted_tasks
            }
            
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    completed += 1
                    if progress_callback:
                        progress_callback(
                            completed,
                            total,
                            f"{result.stock_code} {result.year}: {'OK' if result.success else 'FAIL'}"
                        )
                    
                    # 下载间隔（避免限流）
                    if completed < total:
                        time.sleep(0.5)
                        
                except Exception as e:
                    completed += 1
                    results.append(DownloadResult(
                        stock_code=task.stock_code,
                        year=task.year,
                        success=False,
                        error=str(e)
                    ))
        
        self._results = results
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取下载统计"""
        if not self._results:
            return {"total": 0, "success": 0, "failed": 0, "total_duration_ms": 0}
        
        return {
            "total": len(self._results),
            "success": sum(1 for r in self._results if r.success),
            "failed": sum(1 for r in self._results if not r.success),
            "total_duration_ms": sum(r.duration_ms for r in self._results),
            "avg_duration_ms": sum(r.duration_ms for r in self._results) / len(self._results),
        }


class ParseCache:
    """
    解析结果缓存
    
    使用文件hash作为缓存key
    支持版本控制以自动失效旧缓存
    """
    
    CACHE_VERSION = "1.0"
    
    def __init__(self, cache_dir: str = PARSE_CACHE_DIR):
        self.cache_dir = cache_dir
        ensure_cache_dir()
    
    def _get_file_hash(self, file_path: str) -> str:
        """计算文件MD5 hash"""
        hasher = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            # 如果读取失败，使用文件路径+修改时间作为fallback
            stat = os.stat(file_path)
            return hashlib.md5(f"{file_path}:{stat.st_mtime}".encode()).hexdigest()
    
    def _get_cache_key(self, pdf_path: str) -> str:
        """获取缓存key"""
        file_hash = self._get_file_hash(pdf_path)
        return f"{file_hash}_{self.CACHE_VERSION}"
    
    def _get_cache_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def get(self, pdf_path: str) -> Optional[ParseCacheEntry]:
        """
        获取缓存的解析结果
        
        Args:
            pdf_path: PDF文件路径
        
        Returns:
            缓存条目或None（如果不存在或已失效）
        """
        if not os.path.exists(pdf_path):
            return None
        
        cache_key = self._get_cache_key(pdf_path)
        cache_path = self._get_cache_path(cache_key)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return ParseCacheEntry(**data)
        except Exception:
            return None
    
    def set(self, pdf_path: str, extracted_data: Dict, confidence: float):
        """
        保存解析结果到缓存
        
        Args:
            pdf_path: PDF文件路径
            extracted_data: 提取的数据
            confidence: 置信度
        """
        cache_key = self._get_cache_key(pdf_path)
        cache_path = self._get_cache_path(cache_key)
        
        entry = ParseCacheEntry(
            pdf_path=pdf_path,
            pdf_hash=self._get_file_hash(pdf_path),
            extracted_data=extracted_data,
            confidence=confidence,
            cached_at=datetime.now().isoformat(),
            version=self.CACHE_VERSION
        )
        
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(entry.__dict__, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"缓存写入失败: {e}")
    
    def invalidate(self, pdf_path: str = None):
        """
        使缓存失效
        
        Args:
            pdf_path: 如果指定，只删除该文件的缓存；否则删除所有缓存
        """
        if pdf_path:
            cache_key = self._get_cache_key(pdf_path)
            cache_path = self._get_cache_path(cache_key)
            if os.path.exists(cache_path):
                os.remove(cache_path)
        else:
            # 删除所有缓存
            for f in os.listdir(self.cache_dir):
                if f.endswith(".json"):
                    os.remove(os.path.join(self.cache_dir, f))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        files = [f for f in os.listdir(self.cache_dir) if f.endswith(".json")]
        total_size = sum(
            os.path.getsize(os.path.join(self.cache_dir, f))
            for f in files
        )
        
        return {
            "count": len(files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
        }


class CachedExtractor:
    """
    带缓存的提取器
    
  封装现有提取器，自动使用缓存
    """
    
    def __init__(self, cache_enabled: bool = True):
        self.cache = ParseCache() if cache_enabled else None
    
    def extract_with_cache(
        self,
        pdf_path: str,
        extractor_class,
        force_reextract: bool = False
    ) -> Dict[str, Any]:
        """
        带缓存的提取
        
        Args:
            pdf_path: PDF文件路径
            extractor_class: 提取器类
            force_reextract: 是否强制重新提取
        
        Returns:
            提取结果
        """
        # 检查缓存
        if not force_reextract and self.cache:
            cached = self.cache.get(pdf_path)
            if cached:
                print(f"[CACHE HIT] {pdf_path}")
                return {
                    "data": cached.extracted_data,
                    "confidence": {"overall": cached.confidence},
                    "from_cache": True
                }
        
        print(f"[EXTRACT] {pdf_path}")
        
        # 执行提取
        from extraction.parsers.pdf_parser import PdfParser
        from extraction.extractors.balance_sheet import BalanceSheetExtractor
        from extraction.extractors.income_statement import IncomeStatementExtractor
        from extraction.extractors.cash_flow import CashFlowExtractor
        
        EXTRACTOR_MAP = {
            "BalanceSheetExtractor": BalanceSheetExtractor,
            "IncomeStatementExtractor": IncomeStatementExtractor,
            "CashFlowExtractor": CashFlowExtractor,
        }
        
        ExtractorClass = EXTRACTOR_MAP.get(extractor_class.__name__, extractor_class)
        
        try:
            with PdfParser(pdf_path) as parser:
                extractor = ExtractorClass(parser)
                result = extractor.extract()
                confidence = extractor.calculate_confidence(result)
                
                # 保存缓存
                if self.cache:
                    self.cache.set(
                        pdf_path,
                        result.get("data", {}),
                        confidence.get("overall", 0.0)
                    )
                
                return {
                    "data": result.get("data", {}),
                    "confidence": confidence,
                    "from_cache": False
                }
        except Exception as e:
            return {
                "data": {},
                "confidence": {"overall": 0.0},
                "error": str(e),
                "from_cache": False
            }


# 便捷函数
def parallel_download_reports(
    reports: List[Dict],
    save_func: Callable,
    max_workers: int = 4
) -> Dict[str, Any]:
    """
    并行下载财报
    
    Args:
        reports: 财报列表
        save_func: 保存路径生成函数 (report) -> file_path
        max_workers: 最大并行数
    
    Returns:
        下载统计
    """
    tasks = []
    
    for report in reports:
        url = report.get("announcement_url", "")
        stock_code = report.get("stock_code", "unknown")
        year = report.get("report_year", 0)
        file_path = save_func(report)
        
        if url:
            tasks.append(DownloadTask(
                stock_code=stock_code,
                year=year,
                url=url,
                file_path=file_path
            ))
    
    downloader = ParallelDownloader(max_workers=max_workers)
    results = downloader.download_batch(tasks)
    
    return downloader.get_stats()


# 性能测试
def benchmark_cache():
    """测试缓存性能"""
    import tempfile
    import shutil
    
    # 创建临时PDF副本用于测试
    test_pdf = "/mnt/f/ai_fin_proj/peri_rept_down/data/by_code/000001/000001_平安银行_2024_年报.pdf"
    
    if not os.path.exists(test_pdf):
        print("测试文件不存在")
        return
    
    cache = ParseCache()
    
    print("缓存性能测试")
    print("=" * 50)
    
    # 测试缓存命中
    print("\n第一次提取（无缓存）...")
    start = time.time()
    cached = cache.get(test_pdf)
    first_time = time.time() - start
    print(f"缓存查询: {first_time*1000:.2f}ms, 命中: {cached is not None}")
    
    # 写入测试缓存
    print("\n写入测试缓存...")
    cache.set(test_pdf, {"test": 123}, 0.95)
    
    # 再次查询
    print("第二次查询（应有缓存）...")
    start = time.time()
    cached = cache.get(test_pdf)
    second_time = time.time() - start
    print(f"缓存查询: {second_time*1000:.2f}ms, 命中: {cached is not None}")
    
    # 打印统计
    print("\n缓存统计:")
    stats = cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # 清理测试缓存
    cache.invalidate(test_pdf)
    print("\n测试缓存已清理")


if __name__ == "__main__":
    benchmark_cache()
