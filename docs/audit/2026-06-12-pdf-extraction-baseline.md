# PDF 提取基线评估报告（Job 1）

**日期**：2026-06-11 ~ 2026-06-12
**分支**：`job1-pdf-extraction-eval`
**计划文件**：`docs/superpowers/plans/2026-06-11-akshare-cf-pipeline-jobs.md`

---

## 1. 测试样本

7 只 A 股 2020 年报 PDF，覆盖 4 个板块：

| 股票 | 名称 | 板块 | RDS CF 项目数 |
|------|------|------|---:|
| 600519 | 贵州茅台 | 上海主板 | 49 |
| 600887 | 伊利股份 | 上海主板 | 55 |
| 002415 | 海康威视 | 深圳中小板 | 56 |
| 000858 | 五粮液 | 深圳主板 | 44 |
| 000002 | 万科A | 深圳主板 | 54 |
| 002475 | 立讯精密 | 深圳中小板 | 54 |
| 300750 | 宁德时代 | 深圳创业板 | 55 |

⚠ 002475 的 `data/pdfs/002475/002475_2020_annual.pdf` 原本是"网上说明会通知"（112KB / 1页）。Job 1.3 期间重新从 cninfo 下载真正的 2020 年报（6.5MB / 232页）替换。

---

## 2. 准确率提升进程

每个 fix 后跑 `python scripts/eval_pdf_extraction.py`，记录每股 `exact_rate` 演化：

| 阶段 | 600519 | 600887 | 002415 | 300750 | 000858 | 002475 | 000002 | 平均 |
|------|---:|---:|---:|---:|---:|---:|---:|---:|
| 基线（旧 extracted JSON） | 63.27 | 54.55 | 53.57 | 45.45 | 36.36 | n/a   | 0.0 | ~42 |
| + JSON 结构兼容（wrapped/flat） | 63.27 | 54.55 | 53.57 | 45.45 | 36.36 | 50.0 | 35.19 | 48 |
| + 名称规范化（"四、" "加：" 前缀, "现金"↔"现金及现金等价物"） | **95.92** | 63.64 | 57.14 | 52.73 | 45.45 | 62.96 | 35.19 | 59 |
| + 重提取（dedup 把 supp 页正确分给 CF） | 95.92 | 80.00 | 76.79 | 69.09 | 68.18 | 62.96 | 35.19 | 70 |
| + 补充资料 pattern 加 "的"+"现金流量表相关情况" | 95.92 | 80.00 | 76.79 | 69.09 | 68.18 | 62.96 | 42.59 | 71 |
| + table_parser 跳过 `55(1)` 注脚标记 | 95.92 | 80.00 | 76.79 | 69.09 | 68.18 | 62.96 | 57.41 | 73 |
| + 别名表 + 括号注释剥离（最终） | **95.92** | 80.00 | **80.36** | 69.09 | 68.18 | 62.96 | 61.11 | **74** |

**最终基线**：7 只股票平均 **74%**，600519 达 **95.92%** 满足计划目标。

---

## 3. 关键 fix 清单（commit-by-commit）

1. **`scripts/eval_pdf_extraction.py`**
   - `load_pdf_extracted`：兼容 wrapped/flat 两种 JSON 结构
   - `_normalize_name`：去前缀序号/冒号/空格、'现金'↔'现金及现金等价物' 同义、剥离括号注释、统一标点
   - `best_match_by_name`：4 级匹配（精确 / 别名 / 规范化相等 / 子串包含）
   - `_RDS_TO_PDF_ALIASES`：处理"投资收益/损失"等命名差异（empirically negate=False）
   - `analyze_failure_modes`：输出 `_failure_modes.md`，分类 no_match / large_error / 占位符

2. **`extraction/extractors/base.py:_find_cf_supplementary_pages`**
   - pattern 加 `r'将净利润调节为经营活动[的]?现金流量'`（"的"可选）
   - pattern 加 `r'现金流量表相关情况'`（万科A 等使用）

3. **`extraction/parsers/table_parser.py:_extract_best_value`**
   - 识别 `55(1)`/`56(3)` 等注脚标记列，跳过
   - 修复 -55x 占位符 bug（000002 万科 PDF p158-161 有附注列 `55(1)`，被 `parse_number` 当负数）

---

## 4. 剩余失败的根因（不是 extractor bug）

调查后发现，剩余 no_match / large_error 主要不是提取错误，而是 **PDF↔RDS 真实 schema 差异**：

| 类型 | 示例 | 影响 |
|------|------|------|
| 项目合并 | 万科 PDF 分开 "加：资产减值损失" + "信用减值损失"，RDS 合并为 "加：资产减值准备"（值=两者和） | 万科 ~3 项 large_error |
| 项目拆分 | 万科 PDF 合并 "无形资产及长期待摊费用摊销"，RDS 分开 "无形资产摊销"+"长期待摊费用摊销" | 万科 2 项 no_match |
| 母公司/合并交错 | 万科 p160-161 是母公司 CF，但被 extractor 当成 p158-159 合并 CF 的延续 | 极少影响 exact_rate |
| 多行 wrapped 标签 | 002475 p201 "固定资产报废损失（收益以"－"\n号填列）" 标签换行，extractor 丢行 | 002475 ~5 项 no_match |
| 期初/期末现金别名 | RDS "现金的期末余额"/"减：现金的期初余额" vs PDF "现金及现金等价物年末余额" | 已在 normalize 中处理同义，仍部分 stocks 未匹配 |

---

## 5. 用户决定（2026-06-11 进度评审）

按用户决定：**"PDF 提取数据的准确性不强求，这块今后再想办法提升。到后续阶段。"**

接受 74% 平均基线，转 Task 1.6 / 1.7 收尾。后续 Job 3 中 PDF 仅作为辅助校验（主推 EM/THS 双跑）。

---

## 6. 回归测试（`tests/test_pdf_extraction_quality.py`）

- 每股 baseline 留 1pp 容差（如 600519 测试线 94.0%）
- 守护：测试 `_no_55x_placeholder_in_extracted`（防止 footnote sentinel bug 回归）
- 守护：测试 `_all_7_stocks_present`（防止股票遗漏）
- 全部 9 个测试 PASS

---

## 7. Job 1 → Job 3 接口

Job 3 (双渠道 EM+THS CF 下载) 使用 PDF 校验时，建议：

1. **600519 类股票**（PDF 提取 ≥ 95%）：可作为独立校验源对照 EM/THS 差异
2. **其余股票**（PDF 提取 60-80%）：
   - PDF 校验仅用于"是否存在大数量级偏差"的发现
   - 不应用于 RDS 标准（schema 不一致）
3. **000002 万科类股票**（PDF 提取 ~60%）：PDF 间接法值与 RDS 真实不同，PDF 校验仅适用于直接法 CF 项

Job 3 的 dual-channel HTML 报告应在标题中标注"PDF 校验有效性等级"。

---

## 8. 后续提升建议（不在 Job 1 范围内）

1. **extractor 多行 label 拼接**：修 `_extract_items_from_text` 处理跨行 label（约 +5pp）
2. **eval 端 schema whitelist**：允许 "1 RDS 项 ↔ N PDF 项合并"（约 +10pp）
3. **母公司 CF 隔离**：避免 supp 页夹带母公司数据（约 +3pp）
4. **公允价值 / 信用减值 别名表完善**（约 +2pp）

预计若全部完成，可达 ~90% 平均（仍不能 100% 因为 RDS 部分股票本身数据缺）。

---

## 附：相关文件

- 评估脚本：`scripts/eval_pdf_extraction.py`
- 评估结果：`tmp/eval_pdf_extraction_2020/_eval_summary.json` / `_failure_modes.md`
- 回归测试：`tests/test_pdf_extraction_quality.py`
- PDF 输入：`data/pdfs/{stock}/{stock}_2020_annual.pdf`（gitignore）
- PDF 输出：`data/extracted/by_code/{stock}/{stock}_2020_cash_flow.json`（gitignore）
