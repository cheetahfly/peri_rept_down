# -*- coding: utf-8 -*-
"""
监控告警系统

功能:
- 错误率监控：跟踪提取失败率
- 置信度监控：当提取质量下降时告警
- 性能监控：跟踪处理时间和资源使用
- 健康检查：定期检查关键组件

告警级别:
- INFO: 正常信息
- WARNING: 需要关注
- ERROR: 需要立即处理
- CRITICAL: 系统不可用
"""

import os
import sys
import time
import json
import psutil
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque


# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """告警"""
    timestamp: str
    level: AlertLevel
    source: str  # 来源模块
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "level": self.level.value,
            "source": self.source,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: str
    name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, max_points: int = 1000):
        self.max_points = max_points
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points))
    
    def record(self, name: str, value: float, tags: Dict[str, str] = None):
        """记录指标"""
        point = MetricPoint(
            timestamp=datetime.now().isoformat(),
            name=name,
            value=value,
            tags=tags or {}
        )
        self._metrics[name].append(point)
    
    def get_recent(self, name: str, minutes: int = 60) -> List[MetricPoint]:
        """获取最近N分钟的指标"""
        if name not in self._metrics:
            return []
        
        cutoff = datetime.now() - timedelta(minutes=minutes)
        cutoff_str = cutoff.isoformat()
        
        return [
            p for p in self._metrics[name]
            if p.timestamp >= cutoff_str
        ]
    
    def get_stats(self, name: str, minutes: int = 60) -> Dict[str, float]:
        """获取统计信息"""
        points = self.get_recent(name, minutes)
        if not points:
            return {"count": 0, "avg": 0, "min": 0, "max": 0}
        
        values = [p.value for p in points]
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }
    
    def get_all_metrics(self) -> Dict[str, List[Dict]]:
        """获取所有指标"""
        return {
            name: [asdict(p) for p in points]
            for name, points in self._metrics.items()
        }


class AlertManager:
    """告警管理器"""
    
    # 告警阈值配置
    THRESHOLDS = {
        "error_rate": 0.1,          # 错误率超过10%
        "confidence_min": 0.7,       # 置信度低于70%
        "extraction_time_max": 30.0, # 单次提取超过30秒
        "disk_usage_max": 0.9,       # 磁盘使用超过90%
        "memory_usage_max": 0.85,    # 内存使用超过85%
        "cache_hit_rate_min": 0.5,   # 缓存命中率低于50%
    }
    
    def __init__(self):
        self.alerts: List[Alert] = []
        self.metrics = MetricsCollector()
        self._last_check: Dict[str, datetime] = {}
    
    def check_error_rate(self, source: str, window_minutes: int = 60) -> Optional[Alert]:
        """检查错误率"""
        total = self.metrics.get_stats(f"{source}.total", window_minutes)
        errors = self.metrics.get_stats(f"{source}.errors", window_minutes)
        
        if total["count"] == 0:
            return None
        
        error_rate = errors["count"] / total["count"] if total["count"] > 0 else 0
        
        if error_rate > self.THRESHOLDS["error_rate"]:
            return Alert(
                timestamp=datetime.now().isoformat(),
                level=AlertLevel.ERROR,
                source=source,
                message=f"错误率过高: {error_rate:.1%}",
                details={
                    "error_rate": error_rate,
                    "total_requests": total["count"],
                    "total_errors": errors["count"],
                    "threshold": self.THRESHOLDS["error_rate"]
                }
            )
        
        return None
    
    def check_confidence(self, source: str, stock_code: str, confidence: float) -> Optional[Alert]:
        """检查置信度"""
        self.metrics.record(
            f"{source}.confidence",
            confidence,
            {"stock_code": stock_code}
        )
        
        if confidence < self.THRESHOLDS["confidence_min"]:
            return Alert(
                timestamp=datetime.now().isoformat(),
                level=AlertLevel.WARNING,
                source=source,
                message=f"提取置信度过低: {confidence:.1%}",
                details={
                    "stock_code": stock_code,
                    "confidence": confidence,
                    "threshold": self.THRESHOLDS["confidence_min"]
                }
            )
        
        return None
    
    def check_extraction_time(self, source: str, stock_code: str, duration_s: float) -> Optional[Alert]:
        """检查提取时间"""
        self.metrics.record(
            f"{source}.extraction_time",
            duration_s,
            {"stock_code": stock_code}
        )
        
        if duration_s > self.THRESHOLDS["extraction_time_max"]:
            return Alert(
                timestamp=datetime.now().isoformat(),
                level=AlertLevel.WARNING,
                source=source,
                message=f"提取时间过长: {duration_s:.1f}秒",
                details={
                    "stock_code": stock_code,
                    "duration_s": duration_s,
                    "threshold": self.THRESHOLDS["extraction_time_max"]
                }
            )
        
        return None
    
    def check_disk_usage(self) -> Optional[Alert]:
        """检查磁盘使用"""
        try:
            usage = shutil.disk_usage("/")
            usage_pct = usage.used / usage.total
            
            if usage_pct > self.THRESHOLDS["disk_usage_max"]:
                return Alert(
                    timestamp=datetime.now().isoformat(),
                    level=AlertLevel.CRITICAL,
                    source="system",
                    message=f"磁盘空间不足: {usage_pct:.1%} 已使用",
                    details={
                        "used_bytes": usage.used,
                        "total_bytes": usage.total,
                        "free_bytes": usage.free,
                        "usage_pct": usage_pct,
                        "threshold": self.THRESHOLDS["disk_usage_max"]
                    }
                )
        except Exception:
            pass
        
        return None
    
    def check_memory_usage(self) -> Optional[Alert]:
        """检查内存使用"""
        try:
            memory = psutil.virtual_memory()
            
            if memory.percent / 100 > self.THRESHOLDS["memory_usage_max"]:
                return Alert(
                    timestamp=datetime.now().isoformat(),
                    level=AlertLevel.WARNING,
                    source="system",
                    message=f"内存使用过高: {memory.percent:.1f}%",
                    details={
                        "used_bytes": memory.used,
                        "total_bytes": memory.total,
                        "percent": memory.percent,
                        "threshold": self.THRESHOLDS["memory_usage_max"] * 100
                    }
                )
        except Exception:
            pass
        
        return None
    
    def add_alert(self, alert: Alert):
        """添加告警"""
        self.alerts.append(alert)
        # 只保留最近100条告警
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    def get_recent_alerts(
        self,
        level: AlertLevel = None,
        minutes: int = 60,
        source: str = None
    ) -> List[Alert]:
        """获取最近告警"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        cutoff_str = cutoff.isoformat()
        
        filtered = [
            a for a in self.alerts
            if a.timestamp >= cutoff_str
        ]
        
        if level:
            filtered = [a for a in filtered if a.level == level]
        
        if source:
            filtered = [a for a in filtered if a.source == source]
        
        return filtered
    
    def clear_old_alerts(self, days: int = 7):
        """清理旧告警"""
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        self.alerts = [a for a in self.alerts if a.timestamp >= cutoff_str]


class HealthChecker:
    """健康检查"""
    
    def __init__(self):
        self.last_check_time: Dict[str, datetime] = {}
        self.last_check_result: Dict[str, bool] = {}
    
    def check_component(self, name: str, check_func) -> bool:
        """
        检查组件健康状态
        
        Args:
            name: 组件名称
            check_func: 检查函数，返回 bool
        
        Returns:
            是否健康
        """
        try:
            result = check_func()
            self.last_check_result[name] = result
            self.last_check_time[name] = datetime.now()
            return result
        except Exception as e:
            self.last_check_result[name] = False
            self.last_check_time[name] = datetime.now()
            return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        return {
            "timestamp": datetime.now().isoformat(),
            "components": {
                name: {
                    "healthy": result,
                    "last_check": self.last_check_time.get(name, None).isoformat()
                        if self.last_check_time.get(name) else None
                }
                for name, result in self.last_check_result.items()
            },
            "overall_healthy": all(self.last_check_result.values())
        }


# 全局实例
_metrics_collector = MetricsCollector()
_alert_manager = AlertManager()
_health_checker = HealthChecker()


# 便捷函数
def record_metric(name: str, value: float, tags: Dict[str, str] = None):
    """记录指标"""
    _metrics_collector.record(name, value, tags)

def record_extraction(
    stock_code: str,
    statement_type: str,
    confidence: float,
    duration_s: float,
    success: bool
):
    """记录提取指标"""
    source = f"extraction.{statement_type}"
    
    # 记录总数
    _metrics_collector.record(f"{source}.total", 1, {"stock_code": stock_code})
    
    # 记录错误
    if not success:
        _metrics_collector.record(f"{source}.errors", 1, {"stock_code": stock_code})
    
    # 记录置信度
    _metrics_collector.record(
        f"{source}.confidence",
        confidence,
        {"stock_code": stock_code}
    )
    
    # 记录时间
    _metrics_collector.record(
        f"{source}.extraction_time",
        duration_s,
        {"stock_code": stock_code}
    )
    
    # 检查告警
    alert = _alert_manager.check_confidence(source, stock_code, confidence)
    if alert:
        _alert_manager.add_alert(alert)
    
    alert = _alert_manager.check_extraction_time(source, stock_code, duration_s)
    if alert:
        _alert_manager.add_alert(alert)

def record_cache_hit(hit: bool):
    """记录缓存命中"""
    _metrics_collector.record("cache.hits", 1 if hit else 0)
    _metrics_collector.record("cache.total", 1)

def get_metrics_summary() -> Dict[str, Any]:
    """获取指标摘要"""
    return {
        "extraction_confidence": _metrics_collector.get_stats("extraction.balance_sheet.confidence", 60),
        "extraction_time": _metrics_collector.get_stats("extraction.balance_sheet.extraction_time", 60),
        "error_rate": _get_error_rate("extraction.balance_sheet", 60),
        "cache_stats": _metrics_collector.get_stats("cache.hits", 60),
        "disk_usage": _get_disk_usage(),
        "memory_usage": _get_memory_usage(),
    }

def _get_error_rate(source: str, minutes: int) -> float:
    """计算错误率"""
    total = _metrics_collector.get_stats(f"{source}.total", minutes)
    errors = _metrics_collector.get_stats(f"{source}.errors", minutes)
    
    if total["count"] == 0:
        return 0.0
    
    return errors["count"] / total["count"]

def _get_disk_usage() -> Dict[str, float]:
    """获取磁盘使用情况"""
    try:
        usage = shutil.disk_usage("/")
        return {
            "used_pct": usage.used / usage.total,
            "free_gb": usage.free / (1024**3)
        }
    except Exception:
        return {}

def _get_memory_usage() -> Dict[str, float]:
    """获取内存使用情况"""
    try:
        memory = psutil.virtual_memory()
        return {
            "used_pct": memory.percent / 100,
            "available_gb": memory.available / (1024**3)
        }
    except Exception:
        return {}

def check_health() -> Dict[str, Any]:
    """执行健康检查"""
    results = {}
    
    # 检查PDF解析器
    def check_pdfplumber():
        try:
            from extraction.parsers.pdf_parser import PdfParser
            return True
        except Exception:
            return False
    results["pdfplumber"] = _health_checker.check_component("pdfplumber", check_pdfplumber)
    
    # 检查提取器
    def check_extractors():
        try:
            from extraction.extractors.balance_sheet import BalanceSheetExtractor
            from extraction.extractors.income_statement import IncomeStatementExtractor
            from extraction.extractors.cash_flow import CashFlowExtractor
            return True
        except Exception:
            return False
    results["extractors"] = _health_checker.check_component("extractors", check_extractors)
    
    # 检查系统资源
    disk_alert = _alert_manager.check_disk_usage()
    if disk_alert:
        _alert_manager.add_alert(disk_alert)
    
    memory_alert = _alert_manager.check_memory_usage()
    if memory_alert:
        _alert_manager.add_alert(memory_alert)
    
    results["disk_space"] = disk_alert is None
    results["memory"] = memory_alert is None
    
    return {
        "timestamp": datetime.now().isoformat(),
        "healthy": all(results.values()),
        "checks": results,
        "recent_alerts": [a.to_dict() for a in _alert_manager.get_recent_alerts(minutes=60)[-5:]]
    }

def get_alerts(level: AlertLevel = None, minutes: int = 60) -> List[Dict]:
    """获取告警列表"""
    alerts = _alert_manager.get_recent_alerts(level=level, minutes=minutes)
    return [a.to_dict() for a in alerts]


# 导出类
__all__ = [
    "AlertLevel",
    "Alert",
    "MetricPoint",
    "MetricsCollector",
    "AlertManager",
    "HealthChecker",
    "record_metric",
    "record_extraction",
    "record_cache_hit",
    "get_metrics_summary",
    "check_health",
    "get_alerts",
]


if __name__ == "__main__":
    # 测试监控告警系统
    print("监控告警系统测试")
    print("=" * 50)
    
    # 记录测试指标
    record_metric("test.metric", 42.0, {"tag": "test"})
    
    # 记录测试提取
    record_extraction(
        stock_code="000001",
        statement_type="balance_sheet",
        confidence=0.95,
        duration_s=2.5,
        success=True
    )
    
    # 健康检查
    print("\n健康检查:")
    health = check_health()
    print(json.dumps(health, indent=2, ensure_ascii=False))
    
    # 指标摘要
    print("\n指标摘要:")
    summary = get_metrics_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    # 最近告警
    print("\n最近告警:")
    alerts = get_alerts(minutes=60)
    print(f"共 {len(alerts)} 条")
    
    print("\n监控告警系统正常")
