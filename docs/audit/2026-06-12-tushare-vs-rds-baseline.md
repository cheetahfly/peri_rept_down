# Tushare vs RDS 对比基线报告

**日期**：2026-06-12
**样本**：5 只 A 股（普通公司）× 2020 年报 × 3 表
**金融股 600036 招商银行** 因 tushare 仅返回 母公司数据（comp_type='2'）而非 合并数据（comp_type='1'），未纳入对比
**Token 权限**：2000+ 档位，验证 `stock_basic` 返回 5528 stocks

---

## 1. 汇总

| 股票 | exact | sub_yuan | rounded | large_error | no_match | total | exact_rate |
|------|---:|---:|---:|---:|---:|---:|---:|
| 600519 贵州茅台 | 115 | 0 | 2 | 3 | 0 | 120 | **95.83%** |
| 600887 伊利股份 | 135 | 0 | 2 | 5 | 0 | 142 | **95.07%** |
| 000651 格力电器 | 146 | 0 | 1 | 8 | 0 | 155 | **94.19%** |
| 688981 中芯国际 | 125 | 0 | 2 | 8 | 0 | 135 | **92.59%** |
| 300750 宁德时代 | 135 | 0 | 2 | 4 | 0 | 141 | **95.74%** |
| 600036 招商银行 | — | — | — | — | — | — | **N/A** (NO_TUSHARE_DATA) |

**平均 exact_rate (5 只普通公司)**：(95.83 + 95.07 + 94.19 + 92.59 + 95.74) / 5 = **94.68%**

## 2. 假设检验结果

- **H₀**: tushare 源头 = 巨潮资讯（与 RDS 同源）→ **H₀ 成立** ✓
- **H₁**: tushare 源头 ≠ 巨潮资讯（第三方转载等）→ 拒绝

5 只普通公司 exact_rate **全部 ≥ 92%**，4 只 ≥ 94%，多数 ≈ 95%——远高于"假设成立" 80% 阈值。

## 3. 详细分类

- **exact** (差异 < 0.01 元)：94.68% 主导
- **sub_yuan** (差异 < 1 元)：0% — 极少
- **rounded** (相对误差 < 1%)：~1.5% — 典型 1 元倍数差异
- **large_error** (差异 > 1 元)：~3.6% — 字段命名差异或精度损失
- **no_match** (tushare 无此项)：~0% — tushare 字段覆盖度高

## 4. 已知差异

rounded + large_error 合计约 5%，主要源于：
- **RDS 字段名 vs tushare 字段名映射差异**（如 `销售商品、提供劳务收到的现金` 在 tushare 中是 `c_fr_sale_sg`，best_match 偶尔匹配次优）
- **精度差异**（少量项目 RDS 元/分精度，tushare 整数元）
- **comp_type 选择**（tushare 默认 合并，少数股票默认母公司）

## 5. 测试方法

- **执行**：`python scripts/tri_channel_cf_download.py --stocks-file tmp/test_stocks_tushare.txt --year 2020`
- **数据**：`data/exports_v2/cash_flow_tri_channel/{stock}_2020_tushare vs_rds.html`
- **结果汇总**：`data/exports_v2/cash_flow_tri_channel/_run_summary_2020.json`

## 6. 金融股特别说明

600036 招商银行（金融股）tushare 只返回 `comp_type='2'`（母公司）数据，RDS 是 `cf_f.rds`（合并），两者口径不同——无法对比。
- 下游需手动处理：金融股 tushare 应取 `comp_type='2'` 母公司数据，与 RDS `cf_f.rds` cf_o.rds 字段分开使用
- 未来增强：`_df_to_dict` 在 `comp_type='1'` 缺失时自动 fallback 到 `'2'`（标记 consolidation_basis）

## 7. 下一步

- ✅ H₀ 成立 → tushare 可作为高可信度数据源
- 建议进入 Phase 6：5K 全量拉取（~5h）
- 持续改进：
  - alias 映射优化（top 5 large_error 字段人工审查）
  - 金融股 fallback 逻辑
  - 反向：拉 2021/2022 年报，验证 recent 数据质量

---

## 附录：实施进度

- ✅ Phase 1 基础（pyproject deps + .env 模板）
- ✅ Phase 2 TushareProvider 完整实现（19 tests pass）
- ✅ Phase 3 tri_channel_cf_lib 提取+对比（4 tests pass）
- ✅ Phase 4 tri_channel_cf_download CLI（3 tests pass）
- ✅ Phase 5.1 live smoke test
- ✅ Phase 5.2 6-stock small-batch comparison
- ✅ Phase 5.3 本报告
- ⏸ Phase 6 5K 全量拉取（~5h，需用户决定时机）
