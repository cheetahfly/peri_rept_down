#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控报告生成器

生成每日/每周监控报告，包含:
- 提取成功率
- 置信度统计
- 错误分析
- 性能趋势
"""

import os
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitoring import (
    get_metrics_summary,
    get_alerts,
    check_health,
    AlertLevel,
    _metrics_collector,
    _alert_manager
)


def generate_daily_report():
    """生成日报"""
    report = {
        "title": "每日提取监控报告",
        "generated_at": datetime.now().isoformat(),
        "period": "过去24小时",
    }
    
    # 健康检查
    health = check_health()
    report["health"] = health
    
    # 指标摘要
    metrics = get_metrics_summary()
    report["metrics"] = metrics
    
    # 告警统计
    alerts_24h = get_alerts(minutes=60*24)
    report["alerts_summary"] = {
        "total": len(alerts_24h),
        "by_level": {
            "critical": sum(1 for a in alerts_24h if a["level"] == "critical"),
            "error": sum(1 for a in alerts_24h if a["level"] == "error"),
            "warning": sum(1 for a in alerts_24h if a["level"] == "warning"),
            "info": sum(1 for a in alerts_24h if a["level"] == "info"),
        }
    }
    
    # 置信度分布
    conf_stats = metrics.get("extraction_confidence", {})
    if conf_stats.get("count", 0) > 0:
        avg_conf = conf_stats.get("avg", 0) * 100
        report["confidence_summary"] = {
            "average": f"{avg_conf:.1f}%",
            "min": f"{conf_stats.get('min', 0) * 100:.1f}%",
            "max": f"{conf_stats.get('max', 0) * 100:.1f}%",
            "samples": conf_stats.get("count", 0),
        }
    else:
        report["confidence_summary"] = {"note": "无数据"}
    
    # 错误分析
    error_rate = metrics.get("error_rate", {})
    report["error_analysis"] = {
        "rate": f"{error_rate * 100:.2f}%" if error_rate else "0%",
        "note": "无错误" if not error_rate else "见告警详情"
    }
    
    # 性能统计
    time_stats = metrics.get("extraction_time", {})
    if time_stats.get("count", 0) > 0:
        report["performance"] = {
            "avg_time": f"{time_stats.get('avg', 0):.2f}秒",
            "max_time": f"{time_stats.get('max', 0):.2f}秒",
            "samples": time_stats.get("count", 0),
        }
    else:
        report["performance"] = {"note": "无数据"}
    
    # 系统资源
    report["system_resources"] = {
        "disk": metrics.get("disk_usage", {}),
        "memory": metrics.get("memory_usage", {}),
    }
    
    return report


def format_markdown_report(report: dict) -> str:
    """格式化Markdown报告"""
    lines = [
        f"# {report['title']}",
        f"\n生成时间: {report['generated_at']}",
        f"统计周期: {report['period']}",
        "\n## 健康状态",
    ]
    
    health = report.get("health", {})
    healthy = health.get("healthy", False)
    lines.append(f"\n{'✅ 系统健康' if healthy else '❌ 系统异常'}")
    
    if health.get("checks"):
        lines.append("\n| 组件 | 状态 |")
        lines.append("|------|------|")
        for name, result in health["checks"].items():
            status = "✅ 正常" if result else "❌ 异常"
            lines.append(f"| {name} | {status} |")
    
    # 指标摘要
    lines.extend(["\n## 提取指标"])
    
    conf = report.get("confidence_summary", {})
    if isinstance(conf, dict) and "note" not in conf:
        lines.extend([
            f"- 平均置信度: {conf.get('average', 'N/A')}",
            f"- 最低置信度: {conf.get('min', 'N/A')}",
            f"- 最高置信度: {conf.get('max', 'N/A')}",
            f"- 样本数: {conf.get('samples', 0)}",
        ])
    else:
        lines.append("- 无数据")
    
    perf = report.get("performance", {})
    if isinstance(perf, dict) and "note" not in perf:
        lines.extend([
            f"\n**性能**",
            f"- 平均耗时: {perf.get('avg_time', 'N/A')}",
            f"- 最大耗时: {perf.get('max_time', 'N/A')}",
        ])
    
    # 告警
    lines.extend(["\n## 告警统计"])
    
    alerts_sum = report.get("alerts_summary", {})
    total_alerts = alerts_sum.get("total", 0)
    lines.append(f"\n总计 {total_alerts} 条告警")
    
    by_level = alerts_sum.get("by_level", {})
    if total_alerts > 0:
        lines.append("\n| 级别 | 数量 |")
        lines.append("|------|------|")
        lines.append(f"| 🔴 Critical | {by_level.get('critical', 0)} |")
        lines.append(f"| 🟠 Error | {by_level.get('error', 0)} |")
        lines.append(f"| 🟡 Warning | {by_level.get('warning', 0)} |")
        lines.append(f"| 🔵 Info | {by_level.get('info', 0)} |")
    
    # 系统资源
    lines.extend(["\n## 系统资源"])
    
    disk = report.get("system_resources", {}).get("disk", {})
    if disk:
        used_pct = disk.get("used_pct", 0) * 100
        free_gb = disk.get("free_gb", 0)
        lines.append(f"\n- 磁盘使用: {used_pct:.1f}%")
        lines.append(f"- 剩余空间: {free_gb:.1f} GB")
    
    memory = report.get("system_resources", {}).get("memory", {})
    if memory:
        used_pct = memory.get("used_pct", 0) * 100
        avail_gb = memory.get("available_gb", 0)
        lines.append(f"- 内存使用: {used_pct:.1f}%")
        lines.append(f"- 可用内存: {avail_gb:.1f} GB")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 60)
    print("监控报告生成")
    print("=" * 60)
    
    # 生成报告
    report = generate_daily_report()
    
    # 打印Markdown格式
    md_report = format_markdown_report(report)
    print("\n" + md_report)
    
    # 保存报告
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d")
    report_file = os.path.join(reports_dir, f"daily_report_{timestamp}.md")
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(md_report)
    
    print(f"\n报告已保存: {report_file}")
    
    # 同时保存JSON格式
    json_file = os.path.join(reports_dir, f"daily_report_{timestamp}.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"JSON数据已保存: {json_file}")
