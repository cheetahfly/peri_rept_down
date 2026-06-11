# PDF 提取 Fix Log（Job 1 Task 1.5）

每次 fix 后跑 `python scripts/eval_pdf_extraction.py`，记录平均 exact_rate 与每股变化。

| Fix | commit | 平均 exact_rate | 关键变化 |
|-----|--------|---:|----------|
| 基线（旧 extracted JSON） | (前序) | 42% | 7 只股票，最高 600519 63.27% |
| 1. eval JSON 结构兼容 | `1af7b681` | 48% | `load_pdf_extracted` 兼容 wrapped/flat 两种结构（000002 从 0% 提到 35%） |
| 2. 名称匹配宽松化 | `e878bf44` | 59% | `_normalize_name` 处理 "四、""加：" 前缀 + 现金同义；600519 一举 95.92% |
| 3. 重提取（dedup 修） | `33593e28` | 70% | 重跑所有 7 只 PDF 提取，使 supp 页面被正确分给 CF（pre-existing extractor 已支持） |
| 4. 补充资料 pattern 加 "的" + "现金流量表相关情况" | `850b5fca` | 71% | `extraction/extractors/base.py` 的 `_find_cf_supplementary_pages`；000002 +7pp |
| 5. table_parser 跳过 `55(1)` 注脚 | `850b5fca` | 73% | `extraction/parsers/table_parser.py` 的 `_extract_best_value`；修 -55x 占位符 bug；000002 +22pp |
| 6. 括号注释剥离 + 别名表 | `e4a29d88` | 74% | `_normalize_name` 剥离 (收益以"－"号填列)；`_RDS_TO_PDF_ALIASES` 处理命名差异 |

## 每股最终结果（fix 后 vs fix 前）

| 股票 | 基线 | 最终 | Δ |
|------|---:|---:|---:|
| 600519 茅台 | 63.27% | **95.92%** | +33 |
| 002415 海康 | 53.57% | 80.36% | +27 |
| 600887 伊利 | 54.55% | 80.00% | +25 |
| 300750 宁德 | 45.45% | 69.09% | +24 |
| 000858 五粮液 | 36.36% | 68.18% | +32 |
| 002475 立讯 | n/a (PDF 错文件) | 62.96% | +63 (vs 0%) |
| 000002 万科A | 0%（错读 placeholder） | 61.11% | +61 |

## Fix 之外但发生的关键事件

1. **002475 PDF 替换**（Task 1.3）：发现 `002475_2020_annual.pdf` 是说明会通知，从 cninfo 重新下载真年报（commit `1af7b681`）
2. **000002 重提取**（Task 1.3）：旧 JSON 是历史 extractor 跑的，重跑获得 wrapped 格式（commit `1af7b681`）
3. **跨股票重提取**（Task 1.5 Fix 3）：发现 extractor 已支持 supp 页面（含间接法），但所有股票 JSON 都是更早 extractor 跑的，需要重跑（commit `33593e28`）

## 剩余未解决问题（用户决定不强求 95%）

按用户决定（2026-06-11 进度评审）："PDF 提取数据的准确性不强求，这块今后再想办法提升"。剩余问题归类：

| 类型 | 例子 | 不解决原因 |
|------|------|----------|
| 项目合并/拆分 schema 差异 | 万科 PDF "资产减值损失"+"信用减值损失" vs RDS "资产减值准备"（值=两者和） | 需 schema whitelist 逻辑，超出 extractor bug 范畴 |
| 多行 wrapped 标签 | 002475 p201 "固定资产报废损失（收益以"－" / 号填列）" 跨行 | 需 `_extract_items_from_text` 重写，复杂 |
| 母公司/合并交错 | 万科 p160-161 是母公司 CF 但被当成合并 CF 延续 | 需独立 supp 检测，extractor 深度改造 |

详细原始失败模式见 `_failure_modes.md`，详细分析见 `docs/audit/2026-06-12-pdf-extraction-baseline.md`。
