# Tushare vs RDS 对比基线报告

**日期**：2026-06-12（待填）
**样本**：6 只 A 股 × 2020 年报 × 3 表
**目的**：验证 Tushare 标榜"源头=巨潮资讯（与 RDS 同源）"声明

---

## 1. 汇总

| 股票 | exact | sub_yuan | rounded | large_error | no_match | total | exact_rate |
|------|---:|---:|---:|---:|---:|---:|---:|
| (待跑) | ... | ... | ... | ... | ... | ... | ... |

**平均 exact_rate**：(待跑)

## 2. 假设检验

- **H₀**: tushare 源头 = 巨潮资讯（与 RDS 同源）
- **H₁**: tushare 源头 ≠ 巨潮资讯（第三方转载等）
- **结论阈值**:
  - exact_rate > 80%：H₀ 成立（tushare 与 RDS 数据基本一致）
  - exact_rate 50-80%：需进一步调查（部分匹配）
  - exact_rate < 50%：H₁ 成立（tushare 不是巨潮资讯源头）

## 3. 详细分类

- **exact** (差异 < 0.01 元)：占 (待跑)%
- **sub_yuan** (差异 < 1 元)：占 (待跑)%
- **rounded** (相对误差 < 1%)：占 (待跑)%
- **large_error** (差异 > 1 元)：占 (待跑)%
- **no_match** (tushare 无此项)：占 (待跑)%

## 4. 已知差异

（如有：列出 "RDS 字段名 vs tushare 字段名" 映射差异的 top 5）

| RDS 字段 | tushare 字段 | 差异说明 |
|----------|-------------|---------|
| (待跑) | (待跑) | (待跑) |

## 5. 测试方法

- **执行**：`python scripts/tri_channel_cf_download.py --stocks-file tmp/test_stocks_tushare.txt --year 2020`
- **数据**：`data/exports_v2/cash_flow_tri_channel/{stock}_2020_tushare_vs_rds.html`
- **结果汇总**：`data/exports_v2/cash_flow_tri_channel/_run_summary_2020.json`
- **测试股票清单** (`tmp/test_stocks_tushare.txt`)：
  ```
  600519 贵州茅台 (上海主板)
  600887 伊利股份 (上海主板)
  000651 格力电器 (深圳主板)
  688981 中芯国际 (科创板)
  300750 宁德时代 (创业板)
  600036 招商银行 (上海主板, 金融股)
  ```

## 6. 下一步

（基于结论）
- 若 H₀ 成立：进入 Phase 6 跑 5K 全量拉取
- 若 H₁ 成立：评估 tushare 是否仍可用（数据可能 OK，但需要独立校验）
- 若 50-80% 中间：分析 top large_error 项找原因（字段命名 / 精度 / 范围差异）

---

## 附录：实施进度

- ✅ TushareProvider 完整实现（19 tests pass）
- ✅ tri_channel_cf_lib 提取 + 对比（4 tests pass）
- ✅ tri_channel_cf_download CLI 完整（7 tests pass）
- ⏸ **Phase 5.1 live smoke test — 需要 TUSHARE_TOKEN**
- ⏸ **Phase 5.2 5-10 只股小批量对比 — 需要 TUSHARE_TOKEN**
- ⏸ **Phase 5.3 本报告填充 — 等 5.2 结果**
- ⏸ **Phase 6 5K 全量拉取 — 需要 TUSHARE_TOKEN + ~5h**
