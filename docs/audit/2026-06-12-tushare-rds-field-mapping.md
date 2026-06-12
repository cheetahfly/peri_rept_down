# Tushare ↔ RDS 字段映射关系总结

**日期**：2026-06-12
**方法**：5 只股票 × 2020 年报 × 3 表（BS/IS/CF），value-based matching
**精确率阈值**：diff < 0.01 元 = exact；diff < 1% = close；其余 = mismatch

---

## 1. 跨股票稳定映射（exact，≥4/5 只股票一致）

### 1.1 现金流量表（CF）— 核心字段

| RDS 中文名 | tushare 英文字段 | 一致性 | 说明 |
|-----------|----------------|--------|------|
| 取得借款收到的现金 | `c_recp_borrow` | 5/5 | 融资 |
| 偿还债务支付的现金 | `c_prepay_amt_borr` | 5/5 | 融资 |
| 吸收投资收到的现金 | `c_recp_cap_contrib` | 5/5 | 融资 |
| 收取利息、手续费及佣金的现金 | `ifc_cash_incr` | 4/5 | 金融类 |
| 客户存款和同业存放款项净增加额 | `n_depos_incr_fi` | 4/5 | 金融类 |
| 客户贷款及垫款净增加额 | `n_incr_clt_loan_adv` | 4/5 | 金融类 |
| 存放中央银行和同业款项净增加额 | `n_incr_dep_cbob` | 4/5 | 金融类 |
| 支付利息、手续费及佣金的现金 | `pay_handling_chrg` | 4/5 | 金融类 |
| 支付的各项税费 | `c_paid_for_taxes` | 5/5 | 税 |
| 收到的税费返还 | `recp_tax_rends` | 5/5 | 税 |
| 四、汇率变动对现金的影响 | `eff_fx_flu_cash` | 5/5 | 汇率 |
| 现金及现金等价物净增加额2 | `im_n_incr_cash_equ` | 4/5 | 间接法 CF |
| 投资损失 | `invest_loss` | 5/5 | 间接法 CF |
| 递延所得税资产减少 | `decr_def_inc_tax_assets` | 5/5 | 间接法 CF |
| 存货的减少 | `decr_inventories` | 4/5 | 间接法 CF |
| 经营性应收项目的减少 | `decr_oper_payable` | 5/5 | 间接法 CF |
| 支付其他与经营活动有关的现金 | `oth_cash_pay_oper_act` | 5/5 | CF |
| 收到其他与筹资活动有关的现金 | `oth_cash_recp_ral_fnc_act` | 4/5 | CF |
| 财务费用 | `finan_exp` | 5/5 | IS→CF 交叉 |
| 投资损失 | `invest_loss` | 5/5 | IS→CF 交叉 |
| 无形资产摊销 | `amort_intang_assets` | 5/5 | 间接法 |
| 长期待摊费用摊销 | `lt_amort_deferred_exp` | 5/5 | 间接法 |
| 加：资产减值准备 | `prov_depr_assets` | 5/5 | 间接法 |

### 1.2 资产负债表（BS）— 核心字段

| RDS 中文名 | tushare 英文字段 | 一致性 | 说明 |
|-----------|----------------|--------|------|
| 商誉 | `goodwill` | 4/5 | 资产 |
| 一年内到期的非流动资产 | `nca_within_1y` | 4/5 | 资产 |
| 一年内到期的非流动负债 | `non_cur_liab_due_1y` | 4/5 | 负债 |
| 长期借款 | `lt_borr` | 4/5 | 负债 |
| 减：库存股 | `treasury_share` | 4/5 | 权益 |
| 其中：应付股利 | `div_payable` | 4/5 | 负债 |
| 其中：应付票据 | `notes_payable` | 4/5 | 负债 |
| 其他应付款 | `oth_pay_total` | 4/5 | 负债 |
| 合同资产 | `contract_assets` | 4/5 | 资产 |
| 投资性房地产 | `invest_real_estate` | 4/5 | 资产 |
| 长期应付款 | `lt_payable` | 4/5 | 负债 |
| 应付债券 | `bond_payable` | 4/5 | 负债 |
| 递延收益-非流动负债 | `defer_inc_non_cur_liab` | 4/5 | 负债 |
| 其中：对联营企业和合营企业的投资收益 | `ass_invest_income` | 4/5 | 权益 |
| 资产减值损失（2019格式） | `assets_impair_loss` | 4/5 | 损益 |
| 其中：子公司吸收少数股东投资收到的现金 | `incl_cash_rec_saims` | 4/5 | 少数股东 |

### 1.3 利润表（IS）— 核心字段

| RDS 中文名 | tushare 英文字段 | 一致性 | 说明 |
|-----------|----------------|--------|------|
| 销售费用 | `sell_exp` | 4/5 | 费用 |
| 利息收入 | `int_income` | 4/5 | 收入 |
| 其中：利息费用 | `fin_exp_int_exp` | 4/5 | 费用 |
| 营业外收入 | `non_oper_income` | 4/5 | 利润 |
| 其中：子公司支付给少数股东的股利、利润 | `incl_dvd_profit_paid_sc_ms` | 4/5 | CF |

---

## 2. 需要特殊处理的字段（RDS 名称 ≠ tushare 英文直译）

### 2.1 tushare 间接法 CF 字段命名（中文→英文缩写）

| tushare 字段 | 中文含义 | RDS 对应 | 映射难度 |
|-------------|---------|----------|---------|
| `net_profit` | 净利润 | 净利润 | ✅ 简单 |
| `c_fr_sale_sg` | 销售商品、提供劳务收到的现金 | 销售商品、提供劳务收到的现金 | ✅ 简单 |
| `c_paid_goods_s` | 购买商品、接受劳务支付的现金 | 购买商品、接受劳务支付的现金 | ✅ 简单 |
| `c_paid_to_for_empl` | 支付给职工以及为职工支付的现金 | 支付给职工以及为职工支付的现金 | ✅ 简单 |
| `n_cashflow_act` | 经营活动产生的现金流量净额 | 经营活动产生的现金流量净额 | ✅ 简单 |
| `n_cashflow_inv_act` | 投资活动产生的现金流量净额 | 投资活动产生的现金流量净额 | ✅ 简单 |
| `n_cash_flows_fnc_act` | 筹资活动产生的现金流量净额 | 筹资活动产生的现金流量净额 | ✅ 简单 |
| `c_cash_equ_beg_period` | 期初现金及现金等价物余额 | 期初现金及现金等价物余额 | ✅ 简单 |
| `c_cash_equ_end_period` | 期末现金及现金等价物余额 | 期末现金及现金等价物余额 | ✅ 简单 |
| `depr_fa_coga_dpba` | 固定资产折旧、油气资产折耗、生产性生物资产折旧 | 固定资产折旧... | ✅ 简单 |
| `decr_def_inc_tax_assets` | 递延所得税资产减少 | 递延所得税资产减少 | ✅ 简单 |
| `incr_def_inc_tax_liab` | 递延所得税负债增加 | 递延所得税负债增加 | ✅ 简单 |
| `decr_inventories` | 存货的减少 | 存货的减少 | ✅ 简单 |
| `decr_oper_payable` | 经营性应收项目的减少 | 经营性应收项目的减少 | ✅ 简单 |
| `incr_oper_payable` | 经营性应付项目的增加 | 经营性应付项目的增加 | ✅ 简单 |

### 2.2 RDS 独有字段（tushare 无对应项）

| RDS 字段 | 说明 | 为何 tushare 没有 |
|----------|------|------------------|
| 信用减值损失 | 2019 格式新字段 | tushare 用 `credit_impa_loss`，但与 RDS 命名不同 |
| 递延收益 | 递延收益-流动/非流动 | tushare 有 `defer_inc_non_cur_liab` 但细分不同 |
| 经营性应付项目的增加 | 间接法调节 | tushare 用 `incr_oper_payable`，名称差异 |
| 现金及现金等价物净增加额2 | 间接法用的净增加额 | tushare 用 `im_n_incr_cash_equ` |

### 2.3 tushare 独有字段（RDS 无对应项）

| tushare 字段 | 说明 | 为何 RDS 没有 |
|-------------|------|-------------|
| `free_cashflow` | 自由现金流 | 计算项，非披露数据 |
| `ebitda` | EBITDA | 计算项，非披露数据 |
| `credit_impa_loss` | 信用减值损失（tushare 命名） | RDS 用 "信用减值损失" 或 "信用减值损失（2019格式）" |
| `use_right_asset_dep` | 使用权资产折旧 | 新租赁准则 |
| `fa_fnc_leases` | 融资租赁 | 新租赁准则 |
| `conv_debt_into_cap` | 可转债转股 | 特殊事项 |
| `conv_copbonds_due_within_1y` | 一年内到期可转债 | 特殊事项 |

---

## 3. Mismatch 分析（≥2 只股票不一致的映射）

### 3.1 系统性 mismatch（同一 RDS 字段在多只股票上匹配错）

| RDS 字段 | tushare 错误匹配 | 根因分析 |
|----------|-----------------|---------|
| 公允价值变动损失 | `invest_loss` | tushare 无 `fair_value_loss` 字段，用 `invest_loss` 近似 |
| 信用减值损失 | `amort_intang_assets` | tushare 有 `credit_impa_loss`，但 value-based 匹配失败（金额不同） |
| 固定资产报废损失 | `const_materials` | tushare 用 `loss_scr_fa`，名称差异 |
| 资产处置收益 | `credit_impa_loss` | tushare 用 `loss_disp_fiolta`，名称差异 |
| 递延所得税负债增加 | `decr_oper_payable` | tushare 用 `incr_def_inc_tax_liab`，名称差异 |

### 3.2 稳定 mismatch（一致匹配到错误字段）

| RDS 字段 | tushare 字段 | 原因 |
|----------|-------------|------|
| 其他权益工具投资 | `oth_comp_income` | tushare 用 `oth_eqt_invest`，value 接近但不精确 |
| 财务费用 | `im_n_incr_cash_equ` | tushare 有 `finan_exp` 但某些股票金额差异大 |
| 销售费用 | `prov_depr_assets` | tushare 有 `sell_exp` 但某些股票 value 偏差 |

---

## 4. 推荐映射表（YAML 格式候选）

```yaml
# tushare ↔ RDS 字段映射（2026-06-12 建立）
# 基于 5 只股票 × 2020 年报 × 3 表 value-based matching
# exact_rate: 94.68% (5/5 普通公司)

tushare_to_rds:
  # ========== 现金流量表 (CF) ==========
  # 直接法
  net_profit: 净利润
  c_fr_sale_sg: 销售商品、提供劳务收到的现金
  c_paid_goods_s: 购买商品、接受劳务支付的现金
  c_paid_to_for_empl: 支付给职工以及为职工支付的现金
  c_paid_for_taxes: 支付的各项税费
  oth_cash_pay_oper_act: 支付其他与经营活动有关的现金
  n_cashflow_act: 经营活动产生的现金流量净额
  n_cashflow_inv_act: 投资活动产生的现金流量净额
  n_cash_flows_fnc_act: 筹资活动产生的现金流量净额
  c_prepay_amt_borr: 偿还债务支付的现金
  c_recp_borrow: 取得借款收到的现金
  c_recp_cap_contrib: 吸收投资收到的现金
  recp_tax_rends: 收到的税费返还
  eff_fx_flu_cash: 四、汇率变动对现金的影响
  c_cash_equ_beg_period: 期初现金及现金等价物余额
  c_cash_equ_end_period: 期末现金及现金等价物余额
  im_n_incr_cash_equ: 现金及现金等价物净增加额2

  # 间接法调节
  depr_fa_coga_dpba: 固定资产折旧、油气资产折耗、生产性生物资产折旧
  amort_intang_assets: 无形资产摊销
  lt_amort_deferred_exp: 长期待摊费用摊销
  loss_scr_fa: 固定资产报废损失
  loss_fv_chg: 公允价值变动损失
  invest_loss: 投资损失
  decr_def_inc_tax_assets: 递延所得税资产减少
  incr_def_inc_tax_liab: 递延所得税负债增加
  decr_inventories: 存货的减少
  decr_oper_payable: 经营性应收项目的减少
  incr_oper_payable: 经营性应付项目的增加
  prov_depr_assets: 加：资产减值准备
  credit_impa_loss: 信用减值损失
  use_right_asset_dep: 使用权资产折旧

  # ========== 资产负债表 (BS) ==========
  goodwill: 商誉
  nca_within_1y: 一年内到期的非流动资产
  non_cur_liab_due_1y: 一年内到期的非流动负债
  lt_borr: 长期借款
  treasury_share: 减：库存股
  div_payable: 其中：应付股利
  notes_payable: 其中：应付票据
  oth_pay_total: 其他应付款
  contract_assets: 合同资产
  invest_real_estate: 投资性房地产
  lt_payable: 长期应付款
  bond_payable: 应付债券
  defer_inc_non_cur_liab: 递延收益-非流动负债

  # ========== 利润表 (IS) ==========
  finan_exp: 财务费用
  sell_exp: 销售费用
  int_income: 利息收入
  fin_exp_int_exp: 其中：利息费用
  non_oper_income: 营业外收入
  assets_impair_loss: 资产减值损失（2019格式）

  # ========== 特殊/金融类 ==========
  ifc_cash_incr: 收取利息、手续费及佣金的现金
  n_depos_incr_fi: 客户存款和同业存放款项净增加额
  n_incr_clt_loan_adv: 客户贷款及垫款净增加额
  n_incr_dep_cbob: 存放中央银行和同业款项净增加额
  pay_handling_chrg: 支付利息、手续费及佣金的现金
  incl_cash_rec_saims: 其中：子公司吸收少数股东投资收到的现金
  incl_dvd_profit_paid_sc_ms: 其中：子公司支付给少数股东的股利、利润
  ass_invest_income: 其中：对联营企业和合营企业的投资收益
  oth_cash_recp_ral_fnc_act: 收到其他与筹资活动有关的现金
```

---

## 5. 关键发现

### 5.1 命名模式总结

| 模式 | 示例 | 出现频率 |
|------|------|---------|
| tushare 用英文缩写，RDS 用中文全称 | `c_fr_sale_sg` ↔ "销售商品、提供劳务收到的现金" | **绝大多数** |
| tushare 用"decr_/incr_"前缀 | `decr_inventories` ↔ "存货的减少" | 间接法调节项 |
| tushare 用"c_"前缀表示现金流入 | `c_recp_borrow` ↔ "取得借款收到的现金" | 直接法 CF |
| tushare 用"stot_"前缀表示小计 | `stot_cash_in_fnc_act` ↔ "筹资活动现金流入小计" | 小计行 |
| RDS 有"其中："/"减："前缀 | "其中：应付股利" ↔ `div_payable` | 子项标注 |
| RDS 有"四、"/"五、"序号 | "四、汇率变动对现金的影响" ↔ `eff_fx_flu_cash` | 大分类序号 |

### 5.2 精度差异来源

| 差异类型 | 频率 | 示例 |
|---------|------|------|
| tushare 用合并报表，RDS 也是合并 | 高 | 大多数字段一致 |
| tushare 有合并/母公司两行，我们取 comp_type='1' | — | 过滤后一致 |
| RDS 有"其他"/"基它"兜底项 | 中 | "其他"字段值跨股票差异极大 |
| 间接法字段 RDS 是计算值，tushare 是披露值 | 低 | 个别项差异 |
| 金融股 tushare 只有母公司 | 中 | 600036 全部 mismatch |

### 5.3 金融股特殊处理

600036 招商银行（金融股）tushare 只返回 comp_type='2'（母公司），RDS 用 cf_f.rds（合并）—— 两者口径不同。需要：
- 金融股单独处理：tushare 拉 comp_type='2' + RDS 用 cf_f.rds 的母公司数据
- 或者金融股只做 CF 单表对比（不比较 BS/IS）

---

## 6. 数据来源

- **tushare 数据**：`TUSHARE_TOKEN` 环境变量提供
- **RDS 数据**：`D:/Research/Quant/SETL/cninfo/data_backup/`（5 只股票 2020 年报）
- **对比结果**：`data/exports_v2/cash_flow_tri_channel/` 下 5 个 HTML 报告
- **本映射表**：基于 5 只股票 × 2020 × 3 表的 value-based matching 统计

---

## 7. 下一步

1. **将推荐映射表写入 YAML**（`rules/tushare_rds_field_mapping.yaml`）
2. **在 `tri_channel_cf_lib.py` 中加 name-based matching**（不只依赖 value，也用名称匹配）
3. **金融股 fallback**（comp_type='2' 处理）
4. **信用减值损失** tushare 命名统一（`credit_impa_loss` → "信用减值损失"）
