# -*- coding: utf-8 -*-
"""把质量评估 markdown 报告转 HTML 并用默认浏览器打开。"""
import os
import sys
import webbrowser
import markdown

MD_PATH = "tmp/akshare_test_600519_2020/_quality_report.md"
HTML_PATH = "tmp/akshare_test_600519_2020/_quality_report.html"

with open(MD_PATH, "r", encoding="utf-8") as f:
    md_text = f.read()

# 使用 tables/fenced_code/toc 扩展
html_body = markdown.markdown(
    md_text,
    extensions=["tables", "fenced_code", "toc", "sane_lists"],
)

css = """
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    max-width: 1100px;
    margin: 0 auto;
    padding: 32px 48px;
    line-height: 1.7;
    color: #24292e;
    background: #fafbfc;
}
h1 {
    color: #1a1a2e;
    border-bottom: 3px solid #1a1a2e;
    padding-bottom: 12px;
    margin-top: 0;
}
h2 {
    color: #0366d6;
    border-bottom: 1px solid #e1e4e8;
    padding-bottom: 6px;
    margin-top: 32px;
}
h3 {
    color: #2c3e50;
    margin-top: 24px;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    border-radius: 6px;
    overflow: hidden;
    font-size: 14px;
}
th {
    background: #f6f8fa;
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    border-bottom: 2px solid #e1e4e8;
    color: #24292e;
}
td {
    padding: 8px 14px;
    border-bottom: 1px solid #f0f3f6;
    vertical-align: top;
}
tr:hover td {
    background: #f6f8fa;
}
td:has(+ td) {
    /* not used widely yet, ignore */
}
/* 数字右对齐 */
td:nth-child(n+3) {
    /* general data column hint */
}
code {
    background: #f1f3f5;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: "SF Mono", "Consolas", "Cascadia Code", monospace;
    font-size: 13px;
    color: #d73a49;
}
pre {
    background: #2d2d2d;
    color: #e6e6e6;
    padding: 16px;
    border-radius: 8px;
    overflow-x: auto;
}
pre code {
    background: transparent;
    color: inherit;
    padding: 0;
}
blockquote {
    border-left: 4px solid #0366d6;
    padding: 8px 16px;
    margin: 16px 0;
    background: #f0f6ff;
    color: #586069;
}
hr {
    border: 0;
    border-top: 1px solid #e1e4e8;
    margin: 28px 0;
}
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
strong { color: #1a1a2e; }
ul, ol { padding-left: 24px; }
li { margin: 4px 0; }
/* 星级评分高亮 */
td:contains("⭐⭐⭐⭐⭐") { background: #e6ffed; }
"""

html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>akshare 现金流量表渠道质量测试报告</title>
<style>
{css}
</style>
</head>
<body>
{html_body}
<hr>
<p style="text-align:center;color:#959da5;font-size:12px;">
Generated from <code>{MD_PATH}</code> by <code>scripts/render_quality_report_html.py</code>
</p>
</body>
</html>
"""

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html_doc)

abs_path = os.path.abspath(HTML_PATH)
print(f"HTML saved: {abs_path}")

# 用默认浏览器打开
url = "file:///" + abs_path.replace("\\", "/")
print(f"Opening: {url}")
webbrowser.open(url)
