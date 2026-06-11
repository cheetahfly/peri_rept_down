# Pipeline Jobs 1/3/4 总结

**完成日期**：2026-06-11
**计划文件**：`docs/superpowers/plans/2026-06-11-akshare-cf-pipeline-jobs.md`

---

## Job 1 — PDF 提取流水线评估 (`job1-pdf-extraction-eval`)

**目标**：让 PDF 提取在 2020 年报上达 ≥95% exact_rate，使其能作为 2022+ 时代独立校验源。

**结果**：平均 74%（600519 达 95.92%）。用户决定不强求 95%，剩余 26pp 为 PDF↔RDS 真实 schema 差异，非 extractor bug。

| 股票 | exact_rate | 备注 |
|------|---:|------|
| 600519 茅台 | **95.92%** | 满足计划目标 |
| 002415 海康 | 80.36% | |
| 600887 伊利 | 80.00% | |
| 300750 宁德 | 69.09% | |
| 000858 五粮液 | 68.18% | |
| 002475 立讯 | 62.96% | 重新下载真正的 2020 年报（旧文件是说明会通知） |
| 000002 万科A | 61.11% | -55x footnote bug 修复后 +22pp |

**11 个 commits、9 个回归测试通过**。报告：`docs/audit/2026-06-12-pdf-extraction-baseline.md`

**关键 fix**：
- `extraction/parsers/table_parser.py`：跳过 `55(1)` 注脚标记列（修 -55x 占位符 bug）
- `extraction/extractors/base.py`：补充资料 pattern 加 "的" + "现金流量表相关情况"
- `scripts/eval_pdf_extraction.py`：4 级名称匹配 + 别名表

---

## Job 3 — 双渠道 CF 下载与不一致报告 (`job3-dual-channel-cf`)

**目标**：(stock, year) 自动调 EM yearly + THS new yearly，生成 CSV + HTML 高亮报告。

**6 个 commits、9 个单元测试通过**。

**端到端结果**（5 只 × 2 年）：

| 股票 | 2020 (exact/err) | 2022 (exact/err) |
|------|---:|---:|
| 600519 | 49/2 | 49/3 |
| 600887 | 55/1 | 55/3 |
| 000651 | 62/1 | 61/2 |
| 688981 | 48/10 | 48/7 |
| 300750 | 56/6 | 53/10 |

HTML 报告含 **⚠ cross-validation warning banner**（提醒用户："互相一致 ≠ 值正确"）。

---

## Job 4 — 金融股专门处理 (`job4-financial-stock-cf`)

**目标**：识别金融股 + 建 EM ↔ RDS 字段映射（避开 em_delisted 接口）。

**4 个 commits、7 个单元测试通过**。

- `rules/financial_stock_codes.yaml`：32 只金融股清单（银行/保险/券商）
- `scripts/build_financial_cf_mapping.py`：value-match-based 映射构建器
- `rules/cf_field_map_financial.yaml`：46/51 招商银行字段映射
- 集成到 `dual_channel_cf_download.py`：自动识别金融股 + 💼 HTML banner

**关键发现**：EM 对金融股使用 **通用列名** 存放银行特有数据（如 `OTHER_ASSET_IMPAIRMENT` 列存 "客户存款" 值）。Value-match 揭示了真实映射。

600036 招商银行 2020 端到端：em=71, ths=58 → 52 exact / 18 large_error / 1 rounded。

---

## 测试总览

```
$ pytest tests/test_pdf_extraction_quality.py tests/test_dual_channel_cf.py tests/test_financial_stock_cf.py
```

- Job 1：9 PASS
- Job 3：9 PASS
- Job 4：7 PASS
- **总计 25 个测试全部 PASS**

---

## 分支与 PR 状态

| 分支 | 状态 | Push |
|------|------|------|
| `job1-pdf-extraction-eval` | 完成，本地 + remote | ✅ pushed |
| `job3-dual-channel-cf` | 完成，仅本地 | ⚠ GitHub 网络问题，需手动重试 push |
| `job4-financial-stock-cf` | 完成，仅本地 | ⚠ 同上 |

PR 创建链接（gh CLI 不可用，需用户手动）：
- Job 1: https://github.com/cheetahfly/peri_rept_down/pull/new/job1-pdf-extraction-eval
- Job 3 / 4 待 push 后获得链接

---

## 关键决策记录

1. **002475 PDF 替换**（Job 1.3）：发现原 `002475_2020_annual.pdf` 是"网上说明会通知"，从 cninfo 下载真正的年报替换
2. **000002 -55x bug 调查**（Job 1.5）：根因是 `parse_number("55(1)")` 把 `(1)` 当负号，返回 -551。修 `_extract_best_value` 识别注脚列
3. **95% 目标未达**（Job 1.7）：用户接受 74% 基线，"PDF 提取数据的准确性不强求，这块今后再想办法提升"
4. **Job 3 ⚠ warning banner**：300750 案例表明 EM/THS 互相一致不等于值正确；HTML 报告必须警示
5. **金融股 EM 字段错配**（Job 4）：EM 对金融股复用非银列名，需 value-match 建映射

---

## 后续工作（不在本次范围内）

1. **PDF 提取增强**（Job 1 后续）：multi-line label 拼接、schema whitelist、母公司 CF 隔离 — 预计可达 ~90%
2. **Job 3 PDF 抽查工具**：对 large_error 项自动从 PDF 校验
3. **Job 4 字段映射扩展**：从单只 600036 扩展到所有银行/保险/券商
4. **Job 3 + 4 PR 推送**：解决 GitHub 网络问题后手动 push
