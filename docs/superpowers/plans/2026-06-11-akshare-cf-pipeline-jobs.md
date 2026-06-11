# akshare CF Pipeline 工作计划 — Job 1/3/4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 2022+ 时代可用的现金流量表下载-校验-处理流水线：评估并改进 PDF 提取模块（Job 1），构建 EM+THS 双渠道下载与不一致告警机制（Job 3），针对金融股建立专门字段映射（Job 4）。

**Architecture:** 三个独立但有依赖的工作流。Job 1 提升 PDF 提取准确率，使其能作为 2022+ 时代的独立校验源。Job 3 实现 EM yearly + THS new yearly 双跑下载，自动比对差异并标红。Job 4 为金融股建立 cf_f schema 专门映射，避开 em_delisted 接口。三个工作均沿用现有项目模块结构（`extraction/`、`scripts/`），不引入新依赖。

**Tech Stack:** Python 3.13, akshare 1.18.47, pyreadr (读 .rds), pandas, pytest。无新依赖。

---

## 0. 背景与上下文（必读）

### 0.1 项目核心约束（来自 CLAUDE.md 与项目记忆）

1. **RDS 数据库范围**：仅覆盖到 2022-Q1（2022-03-31），且部分股票更早就缺失（如 600519 cf_o.rds 最新到 2020-12-31，2021 年报 CF 已不在 RDS）
2. **2022+ 时代约束**：RDS 失效后，**PDF 年报提取是唯一独立校验源**。任何 "akshare 多渠道互相印证" 不能替代独立校验（300750 反例：4 渠道一致都错，集体降级到百元精度）
3. **akshare 精度因股票而异**：同一渠道、同一上市公司、不同年份精度都可能不同 —— 必须**以每次实际下载为准**做校验，不预计算精度等级
4. **指令执行规则**：发现无法按用户指令完成任务时必须汇报并询问，不得擅自切换方案
5. **数据精度要求**：目标精确到元（小数点后 2 位），CSV 必须有 `source` 列

### 0.2 第二次多股测试结论（2026-06-11，5 股 × 5 渠道）

| 股票 | 板块 | EM 精确率 | THS new 精确率 | 特别说明 |
|------|------|---------:|--------------:|---------|
| 000651 格力电器 | 深圳主板 | 100% | 100% | 理想情况 |
| 600887 伊利股份 | 上海主板 | 98.2% | 98.2% | 直接法+间接法均精确到分 |
| 688981 中芯国际 | 上海科创板 | 96.2% | 90.6% | RDS 本身只到千元 |
| 600036 招商银行 | 上海主板(金融) | 90.2% | 78.4% | em_delisted 报错；字段口径不同 |
| **300750 宁德时代** | 深圳创业板 | **0%** | **0%** | **集体降级到百元精度** |

测试归档：`tmp/akshare_test_multi_stocks_2020/_multi_stocks_report.html`

### 0.3 关键代码资产

#### akshare 接口签名
```python
import akshare as ak

# EM 年度 (推荐主力，非金融股 254 列，金融股 316 列)
ak.stock_cash_flow_sheet_by_yearly_em(symbol='SH600519')  # 'SH'/'SZ' 前缀

# EM 按报告期 (推荐主力)
ak.stock_cash_flow_sheet_by_report_em(symbol='SH600519')

# THS 新版按年度 (推荐主力)
ak.stock_financial_cash_new_ths(symbol='600519', indicator='按年度')  # 无前缀

# THS 新版按报告期
ak.stock_financial_cash_new_ths(symbol='600519', indicator='按报告期')

# Sina (无间接法，仅 35 项直接法，但 100% 精确到分)
ak.stock_financial_report_sina(stock='sh600519', symbol='现金流量表')
```

#### 日期格式差异（已踩坑）
- EM `REPORT_DATE`: `"2020-12-31 00:00:00"` (字符串带时分秒)
- THS new `report_date`: `"2020-12-31"` (字符串)
- THS old 报告期: `"2020-12-31"` (字符串) 或 INT 年份 `2020`（按年度时）
- Sina `报告日`: INT `20201231`

#### 关键字段映射（EM 英文 → RDS 中文）
间接法 17 项：
```
NETPROFIT             → F044N 净利润
FA_IR_DEPR            → F046N 固定资产折旧/油气资产折耗/生产性生物资产折旧
OILGAS_BIOLOGY_DEPR   → F046N （别名）
IA_AMORTIZE           → F047N 无形资产摊销
LPE_AMORTIZE          → F048N 长期待摊费用摊销
FA_SCRAP_LOSS         → F050N 固定资产报废损失
FAIRVALUE_CHANGE_LOSS → F051N 公允价值变动损失
INVEST_LOSS           → F053N 投资损失
DT_ASSET_REDUCE       → F054N 递延所得税资产减少
DT_LIAB_ADD           → F055N 递延所得税负债增加
INVENTORY_REDUCE      → F056N 存货的减少
OPERATE_RECE_REDUCE   → F057N 经营性应收项目的减少
OPERATE_PAYABLE_ADD   → F058N 经营性应付项目的增加
NETCASH_OPERATENOTE   → F060N 经营活动产生的现金流量净额2
END_CASH              → F066N 现金的期末余额
BEGIN_CASH            → F067N 现金的期初余额
CCE_ADDNOTE           → F071N 现金及现金等价物净增加额2
（无字段）              → F096N 信用减值损失  -- EM 没提供
```

EM 字段拆分案例：`F013N 支付其他与经营活动有关的现金 = PAY_OTHER_OPERATE + OPERATE_OUTFLOW_OTHER`

#### 项目模块结构
```
extraction/                  # 新版抽取模块（推荐使用）
├── cli.py
├── extractors/
│   ├── cash_flow.py        # CF 抽取主逻辑
│   ├── balance_sheet.py
│   ├── income_statement.py
│   └── indicators.py
├── ground_truth/
│   ├── rds_loader.py       # RDS 加载器
│   ├── comparator.py       # 对比器
│   ├── mapper.py
│   ├── auto_learner.py
│   ├── gap_analyzer.py
│   └── rule_applier.py
├── parsers/                # PDF 解析
├── exporters/              # 输出
└── storage/

astock_fundamentals/         # 旧版模块（部分脚本仍在用，注意不要混淆）
├── core/
├── sources/{rds,pdf,api,guosen}/
├── ground_truth/
└── ...

rules/                       # YAML 规则文件
├── aliases.yaml             # 字段别名映射
├── cf_direct_items.yaml     # 直接法 CF 项目
├── indirect_cf_formulas.yaml # 间接法 CF 公式
├── field_order.yaml
├── section_keywords.yaml
├── skip_items.yaml
├── unit_detection.yaml
├── validation_rules.yaml
└── value_mapping_rules.yaml

data/
├── pdfs/{stock}/{stock}_{year}_annual.pdf  # 原始 PDF
├── extracted/by_code/{stock}/{stock}_{year}_cash_flow.json  # 提取结果
├── exports_v2/             # 清洗后的 wide CSV
├── ground_truth_reports/   # 历次对比报告
└── decode_mappings_by_type.json  # RDS field code → 中文名映射
```

#### RDS 加载器调用示例
```python
from extraction.ground_truth.rds_loader import RdsLoader
loader = RdsLoader('D:/Research/Quant/SETL/cninfo/data_backup')
tidy = loader.load_stock_data_tidy('600519', 2020, 'cash_flow')
annual = [r for r in tidy if r['report_type']=='annual']  # 49 项 item
# tidy 每项: {'stock_code','report_year','report_type','statement_type','item_code','item_name','value','display_order'}
```

#### 已有的 25 + 10 个测试用 CSV（可直接复用）
```
tmp/akshare_test_600519_2020/          # 第一次单股 10 渠道 (600519 2020)
  raw_{01..10}_{channel}.csv
  rds_standard_600519_2020_cf.json
  _quality_report.html / .md / .json
  _consolidated_view.html

tmp/akshare_test_multi_stocks_2020/    # 第二次 5 股 × 5 渠道 (2020)
  raw_{600887|600036|000651|688981|300750}_{em_yearly|em_report|em_delisted|ths_new_report|ths_new_yearly}.csv
  _compare_matrix.json
  _multi_stocks_report.html
```

#### 已有的可复用对比工具函数
```python
# scripts/akshare_cf_test_compare.py 内已实现并已被 multi_compare 复用
from scripts.akshare_cf_test_compare import (
    normalize_value,                 # str/float → float，处理 "1070.24亿"/"516.69万"
    best_match,                      # 给 RDS 值找渠道里最接近的字段，返回 (label, value, diff, rel_err)
    extract_em_2020_values,          # EM CSV → {col_name_en: value}（已硬编码 2020-12-31）
    extract_ths_new_2020_values,     # THS new CSV → {metric_name_en: value}
    extract_ths_old_2020_values,
    extract_sina_2020_values,
)
```

⚠ 上述 `extract_*_2020_values` 是 600519 测试时写死了 2020-12-31。Job 3 实现时需要参数化年份。

### 0.4 PDF 现状

已下载的 2020 年报 PDF（位于 `data/pdfs/`）：
- 000002 万科A、000858 五粮液、002415 海康威视、002475 立讯精密
- 300750 宁德时代、600519 贵州茅台、600887 伊利股份

已有提取结果（`data/extracted/by_code/600519/`）：
- 600519_2020_{balance_sheet,cash_flow,income_statement,indicators}.json
- 数据结构：`{stock_code, report_year, statement_type, report_type, data: {statement_type, found, pages, data: {item_name_zh: value}, extracted_at, confidence, recovered, recovery_method}, saved_at}`
- 内层 `data['data']` 是 dict，key 为中文项目名

下载 PDF 脚本：`scripts/batch_pdf_download.py`（需验证当前可用性）

### 0.5 测试数据基准（每股 RDS 标准）
| 股票 | RDS 2020 年报 CF 项目数 | 含间接法 |
|------|---:|---:|
| 600519 贵州茅台 | 49 | 17 |
| 600887 伊利股份 | 55 | 17 |
| 600036 招商银行 (金融) | 51 | 14 |
| 000651 格力电器 | 61 | 15 |
| 688981 中芯国际 | 53 | 14 |
| 300750 宁德时代 | 55 | 16 |

### 0.6 不要做的事

- ❌ 不要预计算"每股精度等级"（用户明确否决） —— 以每次实际下载为准
- ❌ 不要使用 `stock_financial_cash_ths` 旧版（精度仅到亿）
- ❌ 不要把 `stock_cash_flow_sheet_by_report_delisted_em` 用于金融股（会报错）
- ❌ 不要把 `stock_cash_flow_sheet_by_quarterly_em` 用于年度对比（返回单季值）
- ❌ 不要假设 Sina 有间接法 CF（缺 14+ 项）
- ❌ 不要"擅自切换方案"——遇到任何阻塞先汇报用户

### 0.7 Git 提交约定

- 每个 task 完成后提交一次（commit-as-you-go）
- 数据文件与脚本文件分开提交
- commit message 用约定式：`feat(job1):...` / `fix(job3):...` / `test(job4):...`
- 不要在 master 分支直接提交，先 `git checkout -b job1-pdf-extraction-eval`（或类似）

---

## 文件结构

### 新增文件

```
docs/superpowers/plans/2026-06-11-akshare-cf-pipeline-jobs.md  # 本文件

# Job 1
scripts/eval_pdf_extraction.py            # PDF 提取准确率评估器
docs/audit/2026-06-12-pdf-extraction-baseline.md  # 评估基线报告
（按需修改）extraction/extractors/cash_flow.py   # 改进 CF 提取规则
（按需修改）rules/aliases.yaml             # 添加缺失的别名
（按需修改）rules/cf_direct_items.yaml     # 完善直接法项目
（按需修改）rules/indirect_cf_formulas.yaml # 完善间接法公式
tests/test_pdf_extraction_quality.py      # 提取质量回归测试

# Job 3
scripts/dual_channel_cf_download.py       # 双渠道下载主脚本
scripts/dual_channel_cf_lib.py            # 提取/匹配/标红工具函数库
data/exports_v2/cash_flow_dual_channel/   # 输出目录（仅创建）
tests/test_dual_channel_cf.py             # 单元测试

# Job 4
scripts/financial_stock_cf.py             # 金融股专用下载器
rules/financial_stock_codes.yaml          # 金融股代码清单
rules/cf_field_map_financial.yaml         # 金融股 EM 字段 → RDS 字段映射
tests/test_financial_stock_cf.py          # 单元测试
```

### 修改的现有文件

- `CLAUDE.md`：测试完成后追加"流水线已就绪"说明（任务结束时）
- `extraction/extractors/cash_flow.py`：仅在 Job 1 发现具体问题时修改

---

## Job 1: 评估并改进 PDF 提取流水线

**目标：** 在 2022+ 时代 PDF 成为唯一独立校验源前，把 CF 提取在已有 RDS 校准的 2020 年报上做到 ≥95% 精确率（含间接法）。

### Task 1.1: 创建工作分支并准备评估脚本骨架

**Files:**
- Create: `scripts/eval_pdf_extraction.py`

- [ ] **Step 1: 创建工作分支**

```bash
git checkout master
git pull
git checkout -b job1-pdf-extraction-eval
```

Expected: `Switched to a new branch 'job1-pdf-extraction-eval'`

- [ ] **Step 2: 创建评估脚本骨架**

```python
# scripts/eval_pdf_extraction.py
# -*- coding: utf-8 -*-
"""
PDF 提取质量评估：将 data/extracted/by_code/{stock}/{stock}_{year}_cash_flow.json
与 RDS 标准对比，统计精确率、覆盖率、间接法完整性。

测试样本：所有 data/pdfs/{stock}/{stock}_2020_annual.pdf 对应已提取的股票
基准：RDS cf_o.rds / cf_f.rds 的 2020 年报 CF 数据
"""
import os
import sys
import json
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extraction.ground_truth.rds_loader import RdsLoader

RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
EXTRACTED_DIR = "data/extracted/by_code"
OUT_DIR = "tmp/eval_pdf_extraction_2020"
os.makedirs(OUT_DIR, exist_ok=True)


def load_pdf_extracted(stock_code, year):
    """读取 PDF 提取结果，返回 {item_name_zh: value} 或 None"""
    path = os.path.join(EXTRACTED_DIR, stock_code, f"{stock_code}_{year}_cash_flow.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        outer = json.load(f)
    data = outer.get("data", {}).get("data", {})
    # data 是 {item_name_zh: value or None}
    out = {}
    for name, v in data.items():
        if isinstance(v, (int, float)):
            out[name] = float(v)
        elif isinstance(v, str):
            try:
                out[name] = float(v.replace(",", ""))
            except ValueError:
                pass
    return out


def best_match_by_name(rds_name, pdf_data):
    """按字符串相似度匹配；返回 (matched_name, value) 或 (None, None)"""
    if rds_name in pdf_data:
        return rds_name, pdf_data[rds_name]
    # 简化匹配：去空格、冒号后再尝试
    norm_rds = rds_name.replace(" ", "").replace("：", "").replace(":", "")
    for name, v in pdf_data.items():
        if name.replace(" ", "").replace("：", "").replace(":", "") == norm_rds:
            return name, v
    return None, None


def evaluate_stock(stock_code, year=2020):
    loader = RdsLoader(RDS_DIR)
    tidy = loader.load_stock_data_tidy(stock_code, year, "cash_flow")
    rds_annual = [r for r in tidy if r["report_type"] == "annual" and r["value"] is not None]
    pdf_data = load_pdf_extracted(stock_code, year)
    if pdf_data is None:
        return {"stock_code": stock_code, "status": "PDF_NOT_EXTRACTED"}
    counters = {"exact": 0, "sub_yuan": 0, "rounded": 0, "large_error": 0, "no_match": 0}
    rows = []
    for item in rds_annual:
        name, val = best_match_by_name(item["item_name"], pdf_data)
        if val is None:
            counters["no_match"] += 1
            cls = "no_match"
            diff = None; rel = None
        else:
            diff = abs(val - item["value"])
            rel = (diff / abs(item["value"]) * 100) if item["value"] != 0 else 0
            if diff < 0.01: cls = "exact"; counters["exact"] += 1
            elif diff < 1.0: cls = "sub_yuan"; counters["sub_yuan"] += 1
            elif rel < 1.0: cls = "rounded"; counters["rounded"] += 1
            else: cls = "large_error"; counters["large_error"] += 1
        rows.append({
            "rds_code": item["item_code"], "rds_name": item["item_name"],
            "rds_value": item["value"], "pdf_name": name, "pdf_value": val,
            "abs_diff": diff, "rel_err_pct": rel, "class": cls,
        })
    total = sum(counters.values())
    return {
        "stock_code": stock_code, "status": "OK",
        "rds_total": total,
        **counters,
        "exact_rate": round(counters["exact"] / total * 100, 2) if total else 0,
        "details": rows,
    }


def main():
    # 从 data/pdfs 推断已下载 PDF 的股票
    candidates = []
    pdf_root = "data/pdfs"
    for entry in os.listdir(pdf_root):
        d = os.path.join(pdf_root, entry)
        if os.path.isdir(d):
            pdf_path = os.path.join(d, f"{entry}_2020_annual.pdf")
            if os.path.exists(pdf_path):
                candidates.append(entry)
    print(f"Found {len(candidates)} stocks with 2020 PDF: {candidates}")

    results = []
    for stock_code in sorted(candidates):
        r = evaluate_stock(stock_code, 2020)
        results.append(r)
        if r["status"] == "OK":
            print(f"  {stock_code}: exact={r['exact']}/{r['rds_total']} ({r['exact_rate']}%)  "
                  f"no_match={r['no_match']}  large_error={r['large_error']}")
        else:
            print(f"  {stock_code}: {r['status']}")

    out_path = os.path.join(OUT_DIR, "_eval_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSummary: {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 提交骨架**

```bash
git add scripts/eval_pdf_extraction.py
git commit -m "feat(job1): add PDF extraction evaluator scaffold"
```

---

### Task 1.2: 跑评估，建立提取质量基线

**Files:**
- Modify: `scripts/eval_pdf_extraction.py:1-130`（如有 bug 修复）
- Create: `tmp/eval_pdf_extraction_2020/_eval_summary.json`

- [ ] **Step 1: 运行评估**

```bash
PYTHONIOENCODING=utf-8 python scripts/eval_pdf_extraction.py 2>&1 | tee tmp/eval_pdf_extraction_2020/_run.log
```

Expected output: 每只股票一行 exact 数 + 比率。可能多数股票 `PDF_NOT_EXTRACTED`（除了 600519 已有提取结果）。

- [ ] **Step 2: 提交基线结果**

```bash
git add tmp/eval_pdf_extraction_2020/
git commit -m "test(job1): PDF extraction baseline (initial — most stocks not yet extracted)"
```

---

### Task 1.3: 补齐 PDF 提取（对已下载的 7 只股票全部跑提取）

**Files:**
- 使用现有：`scripts/batch_extract.py` 或 `extraction/cli.py`
- Output: `data/extracted/by_code/{stock}/{stock}_2020_cash_flow.json` × 7

- [ ] **Step 1: 检查 batch_extract.py 的调用方式**

Run: `head -50 scripts/batch_extract.py`
Look for: 是否接受 stock_code 参数；是否有 main entry；依赖哪个 extractor

- [ ] **Step 2: 跑 600519 之外的 6 只**

候选清单（已下载 2020 PDF）：
```
000002  万科A
000858  五粮液
002415  海康威视
002475  立讯精密
300750  宁德时代
600887  伊利股份
```

尝试调用方式（若现有脚本支持单股）：
```bash
for code in 000002 000858 002415 002475 300750 600887; do
    PYTHONIOENCODING=utf-8 python scripts/batch_extract.py --stock $code --year 2020 2>&1 | tail -5
done
```

若现有脚本不支持单股调用，向用户汇报：
> "现有 batch_extract.py 不接受单股参数，需要修改脚本或写新的单股提取入口。请确认。"

不要擅自重写整个 batch_extract.py。

- [ ] **Step 3: 验证 6 只都已生成 _cash_flow.json**

```bash
for code in 000002 000858 002415 002475 300750 600887; do
    ls -la data/extracted/by_code/$code/${code}_2020_cash_flow.json 2>&1
done
```

Expected: 6 个文件都存在

- [ ] **Step 4: 重跑评估**

```bash
PYTHONIOENCODING=utf-8 python scripts/eval_pdf_extraction.py 2>&1 | tee tmp/eval_pdf_extraction_2020/_run_v2.log
```

- [ ] **Step 5: 提交**

```bash
git add data/extracted/by_code/ tmp/eval_pdf_extraction_2020/
git commit -m "feat(job1): extract 6 more stocks 2020 CF + re-baseline"
```

---

### Task 1.4: 分析失败模式，找出 top 5 提取错误

**Files:**
- Create: `tmp/eval_pdf_extraction_2020/_failure_modes.md`

- [ ] **Step 1: 生成失败模式分析**

```python
# 加在 scripts/eval_pdf_extraction.py 末尾的辅助函数（或新建分析脚本）
def analyze_failure_modes(summary_path, out_md_path):
    import json, collections
    with open(summary_path, 'r', encoding='utf-8') as f:
        results = json.load(f)
    # 按 rds_name 聚合失败次数
    no_match_counter = collections.Counter()
    large_err_counter = collections.Counter()
    for r in results:
        if r.get('status') != 'OK': continue
        for d in r.get('details', []):
            if d['class'] == 'no_match':
                no_match_counter[d['rds_name']] += 1
            elif d['class'] == 'large_error':
                large_err_counter[d['rds_name']] += 1
    with open(out_md_path, 'w', encoding='utf-8') as f:
        f.write("# PDF 提取失败模式分析\n\n## Top 10 'no_match' (PDF 中没找到对应项目)\n\n")
        for name, cnt in no_match_counter.most_common(10):
            f.write(f"- ({cnt} stocks) {name}\n")
        f.write("\n## Top 10 'large_error' (找到了但值差很多)\n\n")
        for name, cnt in large_err_counter.most_common(10):
            f.write(f"- ({cnt} stocks) {name}\n")
```

Run 后产出 `_failure_modes.md`

- [ ] **Step 2: 人工审查 top failures，对每个失败决定**

对每条 top failure 决定：
- "字段在 PDF 里存在但别名没收录" → 在 `rules/aliases.yaml` 加别名
- "PDF 里就没这项" → 跳过或在 `rules/skip_items.yaml` 标记
- "数值识别错误（单位/符号/小数点）" → 修 `extraction/extractors/cash_flow.py` 或 `rules/unit_detection.yaml`

不知道怎么决定时，向用户汇报：
> "Top 失败项目 X 在 PDF 中存在但提取错误，可能的原因是 A/B/C，请问采用哪种修复策略？"

- [ ] **Step 3: 提交分析**

```bash
git add tmp/eval_pdf_extraction_2020/_failure_modes.md scripts/eval_pdf_extraction.py
git commit -m "test(job1): analyze top failure modes in PDF extraction"
```

---

### Task 1.5: 修改抽取规则，重测验证

**Files:**
- Modify: `rules/aliases.yaml`（加缺失别名）
- Modify: `rules/cf_direct_items.yaml`（按需）
- Modify: `rules/indirect_cf_formulas.yaml`（按需）
- Modify: `extraction/extractors/cash_flow.py`（仅在 YAML 无法解决时）

- [ ] **Step 1: 修改规则（每次只动一个 fix）**

对 Task 1.4 找到的每个 fix：
1. 在对应 YAML 里加规则
2. 重跑评估 `python scripts/eval_pdf_extraction.py`
3. 比对前后 exact_rate

记录到 `tmp/eval_pdf_extraction_2020/_fix_log.md`：
```
## Fix 1: 加别名 "支付的各项税费"
- 之前: 17 stocks 缺这项
- 之后: 0 stocks 缺，全部 exact
- commit: ${hash}

## Fix 2: ...
```

- [ ] **Step 2: 单次 fix 提交（每次一个 fix）**

```bash
git add rules/aliases.yaml tmp/eval_pdf_extraction_2020/
git commit -m "fix(job1): add alias for 'X' (improves N stocks)"
```

- [ ] **Step 3: 达到 ≥95% exact_rate 或汇报阻塞**

目标：7 只股票的平均 exact_rate ≥ 95%

若达不到（如有顽固的 PDF 结构问题），向用户汇报：
> "PDF 提取在 N 只股票上的 exact_rate 是 X%，剩余的 Y 个失败项目是 [清单]，需要改 extractor 代码 / 跳过 / 接受现状，请指示。"

---

### Task 1.6: 加回归测试

**Files:**
- Create: `tests/test_pdf_extraction_quality.py`

- [ ] **Step 1: 写回归测试**

```python
# tests/test_pdf_extraction_quality.py
import json
import os
import pytest

EXTRACTED_DIR = "data/extracted/by_code"
# 已知精确率基线（从 Task 1.5 跑出来的实际值填入）
EXPECTED_BASELINE = {
    "600519": 95.0,  # 占位 — 改成实际跑出来的值
    "600887": 95.0,
    "000651": 95.0,  # 未必有 PDF，先列上
    # ...
}

def load_eval():
    path = "tmp/eval_pdf_extraction_2020/_eval_summary.json"
    if not os.path.exists(path):
        pytest.skip("eval summary not yet generated; run scripts/eval_pdf_extraction.py first")
    with open(path, "r", encoding="utf-8") as f:
        return {r["stock_code"]: r for r in json.load(f) if r.get("status") == "OK"}

@pytest.mark.parametrize("stock_code,min_rate", list(EXPECTED_BASELINE.items()))
def test_extraction_meets_baseline(stock_code, min_rate):
    results = load_eval()
    if stock_code not in results:
        pytest.skip(f"{stock_code} not in eval results")
    actual = results[stock_code]["exact_rate"]
    assert actual >= min_rate, f"{stock_code} exact_rate dropped: {actual}% < baseline {min_rate}%"
```

- [ ] **Step 2: 运行测试**

```bash
PYTHONIOENCODING=utf-8 pytest tests/test_pdf_extraction_quality.py -v
```

Expected: PASS（所有股票达标）

- [ ] **Step 3: 提交**

```bash
git add tests/test_pdf_extraction_quality.py
git commit -m "test(job1): add PDF extraction quality regression test"
```

---

### Task 1.7: 撰写基线报告并合并到 master

**Files:**
- Create: `docs/audit/2026-06-12-pdf-extraction-baseline.md`

- [ ] **Step 1: 写报告**

内容应包括：
- 测试股票清单与板块分布
- 改进前后的 exact_rate 对比
- 已知的剩余失败项（whitelist 例外）
- Job 1 与 Job 3 的接口（PDF 提取作为 Job 3 校验源时怎么用）

- [ ] **Step 2: 合并**

```bash
git push -u origin job1-pdf-extraction-eval
gh pr create --title "Job 1: PDF extraction baseline & improvements" --body "See docs/audit/2026-06-12-pdf-extraction-baseline.md"
# 等用户审查/合并；不要自己直接 merge
```

- [ ] **Step 3: 汇报用户**

> "Job 1 已完成，提取准确率从 X% 提升到 Y%，PR 已创建。是否进入 Job 3？"

---

## Job 3: 双渠道下载脚本 + 自动标红不一致项

**目标：** 给定 (stock, year)，自动调 EM yearly + THS new yearly，对比每一项的差异，输出统一 CSV + 不一致项 HTML 高亮报告。

### Task 3.1: 创建分支并建工具函数库

**Files:**
- Create: `scripts/dual_channel_cf_lib.py`

- [ ] **Step 1: 建分支**

```bash
git checkout master
git pull
git checkout -b job3-dual-channel-cf
```

- [ ] **Step 2: 建工具库（参数化年份版的提取函数）**

```python
# scripts/dual_channel_cf_lib.py
# -*- coding: utf-8 -*-
"""
EM + THS new 双渠道现金流量表对比工具库。

注意：复用 scripts/akshare_cf_test_compare.py 中的 normalize_value/best_match，
但 extract_* 函数需要参数化年份（原版写死 2020）。
"""
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from akshare_cf_test_compare import normalize_value, best_match  # noqa: E402

# EM 排除列（元数据 + YoY）
EM_EXCLUDE = {
    "SECUCODE","SECURITY_CODE","SECURITY_NAME_ABBR","ORG_CODE","ORG_TYPE",
    "REPORT_DATE","REPORT_TYPE","REPORT_DATE_NAME","SECURITY_TYPE_CODE",
    "NOTICE_DATE","UPDATE_DATE","CURRENCY","LISTING_STATE","OPINION_TYPE",
    "OPDATE","OSOPINION_TYPE",
}


def extract_em_year_values(csv_path, year):
    """EM CSV → {col_name_en: value}，提取指定年份年报"""
    df = pd.read_csv(csv_path)
    df["REPORT_DATE"] = df["REPORT_DATE"].astype(str)
    mask = df["REPORT_DATE"].str.startswith(f"{year}-12-31")
    if mask.sum() == 0:
        return {}
    r = df[mask].iloc[0].to_dict()
    out = {}
    for c, v in r.items():
        if c in EM_EXCLUDE or c.endswith("_YOY"):
            continue
        nv = normalize_value(v)
        if nv is not None:
            out[c] = nv
    return out


def extract_ths_new_year_values(csv_path, year):
    """THS new 长格式 CSV → {metric_name: value}"""
    df = pd.read_csv(csv_path)
    df["report_date"] = df["report_date"].astype(str)
    mask = df["report_date"].str.startswith(f"{year}-12-31")
    sub = df[mask]
    out = {}
    for _, row in sub.iterrows():
        name = row.get("metric_name")
        nv = normalize_value(row.get("value"))
        if name and nv is not None:
            out[str(name)] = nv
    return out


def classify_diff(diff, rel_err):
    """返回 (class, color_hint)"""
    if diff is None: return ("no_match", "gray")
    if diff < 0.01: return ("exact", "green")
    if diff < 1.0: return ("sub_yuan", "yellow")
    if rel_err < 1.0: return ("rounded", "orange")
    return ("large_error", "red")


def dual_match(em_values, ths_values):
    """对每个 EM 字段在 THS 中找最佳匹配，返回对照清单。

    返回 list of:
      {em_field, em_value, ths_label, ths_value, abs_diff, rel_err_pct, class, color}
    """
    rows = []
    for em_field, em_v in em_values.items():
        ths_label, ths_v, diff, rel = best_match(em_v, ths_values)
        cls, color = classify_diff(diff, rel)
        rows.append({
            "em_field": em_field, "em_value": em_v,
            "ths_label": ths_label, "ths_value": ths_v,
            "abs_diff": diff, "rel_err_pct": rel,
            "class": cls, "color": color,
        })
    return rows
```

- [ ] **Step 3: 提交**

```bash
git add scripts/dual_channel_cf_lib.py
git commit -m "feat(job3): add dual-channel CF comparison lib"
```

---

### Task 3.2: 写单元测试验证 lib

**Files:**
- Create: `tests/test_dual_channel_cf.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_dual_channel_cf.py
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from dual_channel_cf_lib import (
    extract_em_year_values,
    extract_ths_new_year_values,
    dual_match,
    classify_diff,
)

TEST_DATA = "tmp/akshare_test_600519_2020"


def test_extract_em_year_600519_2020():
    csv_path = os.path.join(TEST_DATA, "raw_01_em_yearly.csv")
    values = extract_em_year_values(csv_path, 2020)
    # 600519 2020 应有约 52 个非空字段
    assert len(values) >= 50
    # 销售商品 = 107,024,384,560.17
    assert any(abs(v - 107024384560.17) < 0.01 for v in values.values())


def test_extract_ths_new_year_600519_2020():
    csv_path = os.path.join(TEST_DATA, "raw_09_ths_new_yearly.csv")
    values = extract_ths_new_year_values(csv_path, 2020)
    assert len(values) >= 40
    # 净利润 = 49,523,329,882.40
    assert any(abs(v - 49523329882.40) < 0.01 for v in values.values())


def test_classify_diff_exact():
    cls, color = classify_diff(0.005, 0)
    assert cls == "exact" and color == "green"


def test_classify_diff_rounded():
    cls, color = classify_diff(50, 0.0001)
    assert cls == "rounded" and color == "orange"


def test_dual_match_600519():
    em_csv = os.path.join(TEST_DATA, "raw_01_em_yearly.csv")
    ths_csv = os.path.join(TEST_DATA, "raw_09_ths_new_yearly.csv")
    em = extract_em_year_values(em_csv, 2020)
    ths = extract_ths_new_year_values(ths_csv, 2020)
    rows = dual_match(em, ths)
    assert len(rows) == len(em)
    exact_count = sum(1 for r in rows if r["class"] == "exact")
    # 600519 EM vs THS new 期望大部分 exact
    assert exact_count >= 35
```

- [ ] **Step 2: 跑测试**

```bash
PYTHONIOENCODING=utf-8 pytest tests/test_dual_channel_cf.py -v
```

Expected: 全部 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_dual_channel_cf.py
git commit -m "test(job3): unit tests for dual-channel CF lib"
```

---

### Task 3.3: 编写双渠道下载主脚本

**Files:**
- Create: `scripts/dual_channel_cf_download.py`

- [ ] **Step 1: 写主脚本**

```python
# scripts/dual_channel_cf_download.py
# -*- coding: utf-8 -*-
"""
双渠道现金流量表下载 + 比对器。

用法：
  python scripts/dual_channel_cf_download.py --stock 600519 --year 2020
  python scripts/dual_channel_cf_download.py --stocks-file stocks.txt --year 2022

输出：
  data/exports_v2/cash_flow_dual_channel/{stock}_{year}_raw_em.csv
  data/exports_v2/cash_flow_dual_channel/{stock}_{year}_raw_ths.csv
  data/exports_v2/cash_flow_dual_channel/{stock}_{year}_merged.csv  # 双渠道合并 + class 标记
  data/exports_v2/cash_flow_dual_channel/{stock}_{year}_report.html # 高亮报告
"""
import os
import sys
import json
import argparse
import warnings
import time

warnings.filterwarnings("ignore")

import akshare as ak
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dual_channel_cf_lib import (
    extract_em_year_values,
    extract_ths_new_year_values,
    dual_match,
)

OUT_DIR = "data/exports_v2/cash_flow_dual_channel"
os.makedirs(OUT_DIR, exist_ok=True)


def em_symbol(code: str) -> str:
    """600/601/603/605/688 → SH; 000/001/002/003/300/301 → SZ; 4/8/9 → BJ"""
    if code.startswith(("600","601","603","605","688")):
        return "SH" + code
    if code.startswith(("000","001","002","003","300","301")):
        return "SZ" + code
    if code.startswith(("4","8","92")):
        return "BJ" + code
    raise ValueError(f"Unknown market for {code}")


def download_one(stock: str, year: int):
    """返回 (em_csv_path, ths_csv_path) 或抛异常"""
    em_sym = em_symbol(stock)
    em_csv = os.path.join(OUT_DIR, f"{stock}_{year}_raw_em.csv")
    ths_csv = os.path.join(OUT_DIR, f"{stock}_{year}_raw_ths.csv")

    df_em = ak.stock_cash_flow_sheet_by_yearly_em(symbol=em_sym)
    df_em.to_csv(em_csv, index=False, encoding="utf-8-sig")

    df_ths = ak.stock_financial_cash_new_ths(symbol=stock, indicator="按年度")
    df_ths.to_csv(ths_csv, index=False, encoding="utf-8-sig")

    return em_csv, ths_csv


def build_merged_csv(stock, year, em_values, ths_values, rows, out_path):
    """合并表：每行一个 EM 字段 + 对应 THS 匹配 + class"""
    df = pd.DataFrame(rows)
    df.insert(0, "stock_code", stock)
    df.insert(1, "report_year", year)
    df.insert(2, "source", "em_yearly+ths_new_yearly")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")


def build_report_html(stock, year, rows, out_path):
    color_css = {
        "exact": "#c8eac8", "sub_yuan": "#f4e4b4", "rounded": "#ffe0a3",
        "large_error": "#f5c2c2", "no_match": "#e8e8e8",
    }
    body = []
    for r in rows:
        bg = color_css.get(r["class"], "#fff")
        em_v = f"{r['em_value']:,.2f}" if r['em_value'] is not None else ""
        ths_v = f"{r['ths_value']:,.2f}" if r['ths_value'] is not None else ""
        diff = f"{r['abs_diff']:,.2f}" if r['abs_diff'] is not None else ""
        rel = f"{r['rel_err_pct']:.2f}%" if r['rel_err_pct'] is not None else ""
        body.append(
            f'<tr style="background:{bg}">'
            f'<td>{r["em_field"]}</td><td class="num">{em_v}</td>'
            f'<td>{r["ths_label"] or ""}</td><td class="num">{ths_v}</td>'
            f'<td class="num">{diff}</td><td class="num">{rel}</td>'
            f'<td>{r["class"]}</td></tr>'
        )
    counts = {}
    for r in rows: counts[r["class"]] = counts.get(r["class"], 0) + 1
    summary_line = " · ".join(f"{k}={v}" for k, v in counts.items())
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{stock} {year} CF EM vs THS new</title>
<style>
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; padding: 20px; }}
h1 {{ color: #1a1a2e; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ padding: 6px 10px; border: 1px solid #e1e4e8; }}
th {{ background: #1a1a2e; color: #fff; }}
.num {{ text-align: right; font-family: Consolas, monospace; }}
.summary {{ background: #fff8db; padding: 12px; border-left: 4px solid #f0ad4e; margin: 12px 0; }}
</style></head><body>
<h1>{stock} - {year} 年报现金流量表 EM vs THS新版 双渠道对比</h1>
<div class="summary"><strong>项目分布：</strong> {summary_line}</div>
<table>
<thead><tr><th>EM 字段</th><th>EM 值</th><th>THS 匹配字段</th><th>THS 值</th>
<th>差异(元)</th><th>相对误差</th><th>类别</th></tr></thead>
<tbody>{"".join(body)}</tbody>
</table>
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def process_stock(stock: str, year: int):
    print(f"\n[{stock} {year}] downloading...")
    try:
        em_csv, ths_csv = download_one(stock, year)
    except Exception as e:
        print(f"  [ERROR] download: {type(e).__name__}: {e}")
        return {"stock": stock, "year": year, "status": "DOWNLOAD_FAILED", "error": str(e)}

    em_v = extract_em_year_values(em_csv, year)
    ths_v = extract_ths_new_year_values(ths_csv, year)
    if not em_v:
        return {"stock": stock, "year": year, "status": "NO_EM_DATA"}
    if not ths_v:
        return {"stock": stock, "year": year, "status": "NO_THS_DATA"}

    rows = dual_match(em_v, ths_v)
    merged_csv = os.path.join(OUT_DIR, f"{stock}_{year}_merged.csv")
    report_html = os.path.join(OUT_DIR, f"{stock}_{year}_report.html")
    build_merged_csv(stock, year, em_v, ths_v, rows, merged_csv)
    build_report_html(stock, year, rows, report_html)

    counts = {}
    for r in rows: counts[r["class"]] = counts.get(r["class"], 0) + 1
    print(f"  [OK] em={len(em_v)} ths={len(ths_v)}  分布: {counts}")
    return {"stock": stock, "year": year, "status": "OK", "counts": counts,
            "merged_csv": merged_csv, "report_html": report_html}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", help="single stock code, e.g. 600519")
    ap.add_argument("--stocks-file", help="text file with one stock code per line")
    ap.add_argument("--year", type=int, required=True, help="report year, e.g. 2022")
    args = ap.parse_args()

    if args.stock:
        stocks = [args.stock]
    elif args.stocks_file:
        with open(args.stocks_file) as f:
            stocks = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    else:
        ap.error("--stock or --stocks-file required")

    results = []
    for code in stocks:
        results.append(process_stock(code, args.year))
        time.sleep(0.5)

    out = os.path.join(OUT_DIR, f"_run_summary_{args.year}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSummary: {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 提交**

```bash
git add scripts/dual_channel_cf_download.py
git commit -m "feat(job3): dual-channel CF download & report generator"
```

---

### Task 3.4: 端到端测试

**Files:**
- 输出到 `data/exports_v2/cash_flow_dual_channel/`

- [ ] **Step 1: 用 5 只测试股票跑一遍**

```bash
for code in 600519 600887 000651 688981 300750; do
    PYTHONIOENCODING=utf-8 python scripts/dual_channel_cf_download.py --stock $code --year 2020
done
```

Expected: 每只股票输出 4 个文件，控制台打印 counts 分布

- [ ] **Step 2: 验证 300750 标红（精度反例）**

```bash
ls data/exports_v2/cash_flow_dual_channel/300750_2020_report.html
# 用浏览器打开看是否大量黄/橙色（rounded 类）
```

Expected: 300750 的 HTML 报告中 `rounded` 类应 ≥ 50 项（因 EM/THS 都集体降级到百元精度，但两者一致 → 内部对比 exact，但 vs RDS rounded — 注意这里是 EM vs THS，可能都是 exact）

实际：EM 与 THS new 在 300750 上**都**降级到百元，所以双方互相对比可能仍 exact。**这正是用户提示的"互相印证不能替代独立校验"的体现**。在报告中应有醒目提示。

- [ ] **Step 3: 在 HTML 报告里加 "互相印证 ≠ 值正确" 警告 banner**

修改 `build_report_html` 在 `<div class="summary">` 上方加：

```python
warning = """<div class="summary" style="border-left-color:#d73a49;background:#ffe0e0;">
<strong>⚠ 重要警告</strong>：本报告仅展示 EM 与 THS 新版的相互一致性。<br>
当两个渠道都集体降级精度时（如 300750 案例），所有项目都会显示 "exact" 但实际数值与真实财报有差异。<br>
<strong>2022+ 数据务必用 PDF 年报抽样校验。</strong>
</div>"""
```

加在主 summary 上面。

- [ ] **Step 4: 提交端到端结果**

```bash
git add data/exports_v2/cash_flow_dual_channel/ scripts/dual_channel_cf_download.py
git commit -m "feat(job3): end-to-end test with 5 stocks 2020 + add cross-validation warning"
```

---

### Task 3.5: 跑一年 2022 真实数据（小批量验证 2022+ 时代）

**Files:**
- 选 5 只代表股，下 2022 年报

- [ ] **Step 1: 准备股票清单**

```bash
cat > tmp/test_stocks_2022.txt <<EOF
600519
600887
000651
688981
300750
EOF
```

- [ ] **Step 2: 跑 2022**

```bash
PYTHONIOENCODING=utf-8 python scripts/dual_channel_cf_download.py --stocks-file tmp/test_stocks_2022.txt --year 2022
```

观察哪些股票 EM 与 THS new 出现 `large_error` —— 这些需要 PDF 抽查。

- [ ] **Step 3: 汇报阶段结果**

向用户汇报：
> "2022 年报双渠道下载完成，5 只股票中 N 只出现 EM/THS 不一致。是否进入 Job 4？或者先做 Job 3 的 PDF 抽查工具？"

不要擅自决定下一步。

- [ ] **Step 4: 推送分支建 PR**

```bash
git push -u origin job3-dual-channel-cf
gh pr create --title "Job 3: Dual-channel CF download & report" --body "..."
```

---

## Job 4: 金融股专门处理

**目标：** 为金融股（银行、保险、券商）建立 EM 字段 → RDS 字段的专门映射；下载脚本自动判断金融股并选用 `cf_f` 路径，避开 em_delisted。

### Task 4.1: 创建分支与金融股代码清单

**Files:**
- Create: `rules/financial_stock_codes.yaml`

- [ ] **Step 1: 建分支**

```bash
git checkout master
git pull
git checkout -b job4-financial-stock-cf
```

- [ ] **Step 2: 编辑金融股清单**

```yaml
# rules/financial_stock_codes.yaml
# A 股主流金融股代码（用于自动识别金融股，选 cf_f schema）
# 数据源：申万一级行业 = 银行、非银金融

banks:
  - "000001"  # 平安银行
  - "002142"  # 宁波银行
  - "600015"  # 华夏银行
  - "600016"  # 民生银行
  - "600036"  # 招商银行
  - "601009"  # 南京银行
  - "601128"  # 常熟银行
  - "601166"  # 兴业银行
  - "601169"  # 北京银行
  - "601229"  # 上海银行
  - "601288"  # 农业银行
  - "601318"  # 中国平安（保险）
  - "601328"  # 交通银行
  - "601398"  # 工商银行
  - "601658"  # 邮储银行
  - "601818"  # 光大银行
  - "601939"  # 建设银行
  - "601988"  # 中国银行
  - "601998"  # 中信银行

insurance:
  - "601318"  # 中国平安（也分类到银行）
  - "601336"  # 新华保险
  - "601601"  # 中国太保
  - "601628"  # 中国人寿
  - "601319"  # 中国人保

securities:
  - "000776"  # 广发证券
  - "600030"  # 中信证券
  - "600837"  # 海通证券
  - "601066"  # 中信建投
  - "601211"  # 国泰君安
  - "601377"  # 兴业证券
  - "601688"  # 华泰证券
  - "601788"  # 光大证券
  - "601881"  # 中国银河
```

- [ ] **Step 3: 提交**

```bash
git add rules/financial_stock_codes.yaml
git commit -m "feat(job4): add financial stock codes registry"
```

---

### Task 4.2: 用一只银行股建立 EM 字段映射基线

**Files:**
- Create: `tmp/eval_financial_cf_2020/`
- Create: `rules/cf_field_map_financial.yaml`

- [ ] **Step 1: 下载 600036 招商银行的 EM 与 RDS 数据**

```bash
PYTHONIOENCODING=utf-8 python -c "
import akshare as ak
df = ak.stock_cash_flow_sheet_by_yearly_em(symbol='SH600036')
df.to_csv('tmp/eval_financial_cf_2020/600036_em_yearly.csv', index=False, encoding='utf-8-sig')
print('cols:', len(df.columns))
print('2020-12-31 行存在:', (df['REPORT_DATE'].astype(str).str.startswith('2020-12-31')).sum())
"
```

Expected: 316 列（金融股有更多字段）

- [ ] **Step 2: 提取 RDS 金融股标准**

```python
# 用脚本 scripts/akshare_cf_test_export_rds.py 的逻辑，针对 600036
PYTHONIOENCODING=utf-8 python -c "
import sys; sys.path.insert(0,'.')
from extraction.ground_truth.rds_loader import RdsLoader
import json
loader = RdsLoader('D:/Research/Quant/SETL/cninfo/data_backup')
tidy = loader.load_stock_data_tidy('600036', 2020, 'cash_flow')
annual = [r for r in tidy if r['report_type']=='annual']
print(f'金融股RDS项目: {len(annual)}')
with open('tmp/eval_financial_cf_2020/600036_rds_standard.json','w',encoding='utf-8') as f:
    json.dump([{'item_code':r['item_code'],'item_name':r['item_name'],'value':float(r['value']) if r['value'] is not None else None} for r in annual], f, ensure_ascii=False, indent=2)
"
```

- [ ] **Step 3: value-based 匹配建立映射候选**

写脚本：对每个 RDS item 在 EM 行中找精确匹配字段（diff < 0.01），输出 `(rds_code, rds_name, em_field, em_value)` 表格。

```python
# scripts/build_financial_cf_mapping.py
import json, pandas as pd, sys, os
sys.path.insert(0, 'scripts')
from akshare_cf_test_compare import normalize_value, best_match

with open('tmp/eval_financial_cf_2020/600036_rds_standard.json','r',encoding='utf-8') as f:
    rds = json.load(f)
df = pd.read_csv('tmp/eval_financial_cf_2020/600036_em_yearly.csv')
mask = df['REPORT_DATE'].astype(str).str.startswith('2020-12-31')
r = df[mask].iloc[0].to_dict()
EXCLUDE = {"SECUCODE","SECURITY_CODE","SECURITY_NAME_ABBR","ORG_CODE","ORG_TYPE","REPORT_DATE","REPORT_TYPE","REPORT_DATE_NAME","SECURITY_TYPE_CODE","NOTICE_DATE","UPDATE_DATE","CURRENCY","LISTING_STATE","OPINION_TYPE","OPDATE"}
em_values = {c: normalize_value(v) for c,v in r.items() if c not in EXCLUDE and not c.endswith('_YOY') and normalize_value(v) is not None}

mapping = []
for item in rds:
    if item['value'] is None: continue
    label, ch_v, diff, rel = best_match(item['value'], em_values)
    if diff is not None and diff < 0.01:
        mapping.append({'rds_code':item['item_code'],'rds_name':item['item_name'],'em_field':label,'em_value':ch_v,'status':'exact'})
    else:
        mapping.append({'rds_code':item['item_code'],'rds_name':item['item_name'],'em_field':label,'em_value':ch_v,'abs_diff':diff,'rel_err':rel,'status':'mismatch'})

import yaml
with open('rules/cf_field_map_financial.yaml','w',encoding='utf-8') as f:
    yaml.safe_dump({'em_to_rds': [{'em_field':m['em_field'],'rds_code':m['rds_code'],'rds_name':m['rds_name']} for m in mapping if m['status']=='exact']}, f, allow_unicode=True, sort_keys=False)
print(f'exact mapped: {sum(1 for m in mapping if m[\"status\"]==\"exact\")}/{len(mapping)}')
print(f'YAML 写入 rules/cf_field_map_financial.yaml')
```

- [ ] **Step 4: 提交**

```bash
git add tmp/eval_financial_cf_2020/ scripts/build_financial_cf_mapping.py rules/cf_field_map_financial.yaml
git commit -m "feat(job4): build financial CF field mapping from 600036 baseline"
```

---

### Task 4.3: 把金融股识别集成到 Job 3 下载脚本

**Files:**
- Modify: `scripts/dual_channel_cf_download.py`（添加金融股分支）

- [ ] **Step 1: 在 `dual_channel_cf_download.py` 顶部加金融股识别**

```python
import yaml

def load_financial_codes():
    with open("rules/financial_stock_codes.yaml") as f:
        d = yaml.safe_load(f)
    s = set()
    for v in d.values():
        if isinstance(v, list):
            s.update(v)
    return s

FINANCIAL_CODES = load_financial_codes()


def is_financial(code: str) -> bool:
    return code in FINANCIAL_CODES
```

- [ ] **Step 2: 在 `process_stock` 里对金融股加标记**

```python
def process_stock(stock: str, year: int):
    is_fin = is_financial(stock)
    print(f"\n[{stock} {year}] {'(金融股)' if is_fin else ''} downloading...")
    # ... 现有逻辑
    # 在返回值里加 is_financial 字段
    return {..., "is_financial": is_fin, ...}
```

`em_delisted` 本来就不在 Job 3 中调用（Job 3 只用 yearly），所以这里不需要避开它。但要在 HTML 报告里加金融股提示。

- [ ] **Step 3: 在 HTML 报告里加金融股 banner**

```python
def build_report_html(stock, year, rows, out_path, is_financial=False):
    fin_warn = ""
    if is_financial:
        fin_warn = """<div class="summary" style="border-left-color:#0366d6;background:#e3f2fd;">
<strong>💼 金融股提示</strong>：该股票为金融股（银行/保险/券商），其 CF schema 与普通股不同（316列 vs 254列）。
RDS 标准数据应使用 cf_f.rds（非 cf_o.rds）。字段映射详见 rules/cf_field_map_financial.yaml。
</div>"""
    # 把 fin_warn 拼到 HTML body 顶部
```

- [ ] **Step 4: 用 600036 端到端验证**

```bash
PYTHONIOENCODING=utf-8 python scripts/dual_channel_cf_download.py --stock 600036 --year 2020
```

打开生成的 `data/exports_v2/cash_flow_dual_channel/600036_2020_report.html` 查看金融股 banner。

- [ ] **Step 5: 提交**

```bash
git add scripts/dual_channel_cf_download.py data/exports_v2/cash_flow_dual_channel/600036_*
git commit -m "feat(job4): integrate financial stock detection into dual-channel download"
```

---

### Task 4.4: 单元测试

**Files:**
- Create: `tests/test_financial_stock_cf.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_financial_stock_cf.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from dual_channel_cf_download import is_financial, FINANCIAL_CODES

def test_600036_is_financial():
    assert is_financial("600036") is True

def test_601318_is_financial():
    assert is_financial("601318") is True  # 中国平安

def test_600030_is_financial():
    assert is_financial("600030") is True  # 中信证券

def test_600519_not_financial():
    assert is_financial("600519") is False  # 贵州茅台

def test_financial_codes_loaded():
    assert len(FINANCIAL_CODES) >= 20
```

- [ ] **Step 2: 跑测试**

```bash
PYTHONIOENCODING=utf-8 pytest tests/test_financial_stock_cf.py -v
```

Expected: 全部 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_financial_stock_cf.py
git commit -m "test(job4): unit tests for financial stock detection"
```

---

### Task 4.5: 收尾 + PR

- [ ] **Step 1: 推送分支**

```bash
git push -u origin job4-financial-stock-cf
gh pr create --title "Job 4: Financial stock specialized CF handling" --body "..."
```

- [ ] **Step 2: 向用户汇报**

> "Job 4 完成。金融股识别清单 X 只，600036 字段映射已建立，下载脚本会自动识别金融股并在报告里加提示。PR 已创建。"

---

## 最终验证 Checklist

完成 Job 1/3/4 后，整体验证：

- [ ] `pytest tests/ -v` 全部 PASS
- [ ] CLAUDE.md 中提到的不要做的事都没做（Section 0.6）
- [ ] 没有擅自切换方案，所有阻塞都有汇报记录
- [ ] 每个 task 都有独立 commit
- [ ] 3 个 PR 已创建，等待用户审查
- [ ] 提交一个简短的总结报告 `docs/audit/2026-06-12-pipeline-jobs-summary.md`

---

## 阻塞汇报模板

任何步骤出现以下情况时立即停止并汇报用户：

| 情况 | 汇报示例 |
|------|---------|
| akshare 接口报错 | "调用 X 接口下载 Y 时返回 Error Z，可能原因是 A/B，请问如何处理？" |
| RDS 数据缺失 | "Y 股票的 Z 年报 RDS 没有数据，无法做基线对比，请问改用其他年份还是其他股票？" |
| 提取规则改不动 | "PDF 提取在 N 项目上失败，可能需要修改 extractor.py，但涉及核心逻辑，请问是否进行？" |
| 接口语义不清 | "akshare 函数 X 的 indicator 参数有 A/B/C 三个选项，文档未说明差异，请问选哪个？" |
| 计划与现状冲突 | "原计划假设文件 X 存在，但实际不存在；现有替代是 Y/Z，请问采用哪个？" |
