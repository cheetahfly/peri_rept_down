# Tushare 数据渠道设计 spec

**日期**：2026-06-12
**状态**：设计通过，待 writing-plans 写实施计划
**目标用户**：A股上市公司财务数据多源清洗流水线 (`peri_rept_down`)

---

## 1. 目标与背景

### 1.1 用户需求
- tushare 作为第 5 个数据渠道（与 RDS、PDF、akshare、Guosen 同级）
- 文档：https://tushare.pro/document/2
- 第一步先搭文件骨架、写代码，然后用户提供 TOKEN
- **核心要求**：与 RDS 对比验证"源头=巨潮资讯"的声明（RDS 也是巨潮资讯源头）

### 1.2 现有上下文
- `astock_fundamentals/sources/api/tushare_provider.py` 已有 48 行骨架（3 个 get_* 全 return None）
- `astock_fundamentals/sources/api/akshare_provider.py` 是 107 行完整实现，可作参考模板
- `astock_fundamentals/sources/api/__init__.py` 已定义 `BaseApiProvider` 基类（3 个抽象方法：BS/IS/CF）
- `astock_fundamentals/sources/rds/rds_loader.py` 提供 `load_stock_data_tidy(stock, year, statement_type)` 用于对比
- `scripts/dual_channel_cf_lib.py` 与 `scripts/dual_channel_cf_download.py` 是 Job 3 的 EM+THS 双渠道实现（可复用 normalize/extract/best_match）

### 1.3 关键约束
| 约束 | 值 |
|------|---|
| Token 权限档位 | 2000（推断，需用户提供） |
| 每分钟最大请求 | 200 次/分钟 |
| 单接口每日上限 | 100,000 次 |
| A 股活跃股票数 | 约 5,000 只 |
| 拉取间隔 | sleep(0.3~0.5)，压到 200/min 以内，否则 403 限流 |
| 验证粒度 | 5-10 只股票 × 多年份 × 3 表（小批量采样） |
| 首次全量 | 5,000 只年报（拿到 token 后手动跑） |

---

## 2. 架构

```
[数据源]                [处理]                    [输出]
akshare (EM+THS)  ──┐
                  ├──> tri_channel_cf_lib.py  ──>  tri_channel_cf_download.py  ──>  data/exports_v2/
tushare (新)     ──┤     extract + match         per-stock × per-year               cash_flow_tri_channel/
                  │      + classify               download + report                  {stock}_{year}_tushare_vs_rds.html
RDS (cninfo)     ──┘                                                             +
                                                                                  {stock}_{year}_tushare_vs_rds.csv
                                                                                  + _run_summary_*.json

  ↓
[全量拉取] download_tushare_full.py → data/exports_v2/tushare_full/{ts}_{year}_{stmt}.csv
```

---

## 3. 组件

### 3.1 `TushareProvider`（完整实现）— `astock_fundamentals/sources/api/tushare_provider.py`

**替换现有 48 行 TODO 骨架**。

**实现要点**：
- 继承 `BaseApiProvider`，实现 3 个 `get_*_statement` 方法
- `_connect()`：懒加载 tushare 库 + `ts.set_token(token)` + `ts.pro_api()`
- `_throttle()`：强制 sleep 间隔（默认 0.4s），通过 `_last_call_ts` 跟踪
- `_fetch(api_name, **kwargs)`：统一调用入口，含 3 次指数退避重试
- `_ts_code(stock_code)`：stock code 转换（`600519` → `600519.SH` 等）
- `_period(year, report_type)`：报告期转换（annual → `20201231` 等）
- `_df_to_dict(df)`：DataFrame → `{item_name: value}` 字典

**错误处理**：
- ImportError：tushare 未安装
- token 缺失：启动立即报错
- 权限/积分不足：不重试
- 403 限流：5s 退避 + 重试 1 次
- 网络错误：3 次指数退避（2s/4s/8s）
- 空 DataFrame（报告期未发布）：返回空 dict，调用方标 NO_DATA

### 3.2 `tri_channel_cf_lib.py` — `scripts/tri_channel_cf_lib.py`

**复用 Job 3 的 normalize/extract/best_match**（从 `scripts/dual_channel_cf_lib.py` 导入）。

**新增**：
- `extract_tushare_year_values(provider, stock_code, year) -> Dict[str, float]`
  - 调用 provider 的 3 个 get_*_statement
  - 用 `[stmt_type] item_name` 前缀避免重名
  - 返回 `{item_name: value}`
- `tri_match(tushare_values, rds_standard) -> List[Dict]`
  - 每个 RDS 项用 `best_match` 找 tushare 中最匹配
  - 返回分类清单（exact/sub_yuan/rounded/large_error/no_match）

### 3.3 `tri_channel_cf_download.py` — `scripts/tri_channel_cf_download.py`

**CLI 接口**：
```
# 显式传 token
python scripts/tri_channel_cf_download.py --stock 600519 --year 2020 --token <TUSHARE_TOKEN>
# 从环境变量 TUSHARE_TOKEN 读（默认行为）
export TUSHARE_TOKEN=<TUSHARE_TOKEN>
python scripts/tri_channel_cf_download.py --stock 600519 --year 2020
# 批量
python scripts/tri_channel_cf_download.py --stocks-file stocks.txt --year 2022
```

**token 解析优先级**：`--token` 参数 > `TUSHARE_TOKEN` 环境变量 > 错误退出

**输出**（每只股 × 每年）：
- `data/exports_v2/cash_flow_tri_channel/{stock}_{year}_raw_tushare.csv`
- `data/exports_v2/cash_flow_tri_channel/{stock}_{year}_tushare_vs_rds.csv`
- `data/exports_v2/cash_flow_tri_channel/{stock}_{year}_tushare_vs_rds.html`

**HTML 报告含双层警告**：
1. 跨渠道一致性警告（沿用 Job 3）
2. **新**：tushare 标榜源头=巨潮资讯，如出现差异可能为 XML→DataFrame 转换损失

### 3.4 `download_tushare_full.py` — `scripts/download_tushare_full.py`

**5,000 只全量拉取**：
- `--years 2020-2022` 年份范围（默认 3 年）
- `--resume` 断点续传（`data/tushare_full_checkpoint.json`）
- `--workers 1` 默认串行（rate limit 必要）
- `--rate-limit-sleep 0.4` 可调
- **单年估算**：5,000 只 × 0.4s sleep × 3 表 = 6,000s = 1.7 小时
- **3 年估算**：5,000 × 3 × 0.4 × 3 = 18,000s = 5 小时
- 远低于 100,000/天日上限（即使 3 年也只需 ~45K 请求）

**输出**：`data/exports_v2/tushare_full/{ts_code}_{year}_{stmt}.csv`

### 3.5 测试

**A. `test_tushare_provider.py`** — mock tushare 库
- `_connect()` 成功/失败（ImportError）
- `_throttle()` 间隔控制
- `_ts_code()` 转换
- `_period()` 转换
- `_fetch()` 重试（指数退避）
- `_df_to_dict()` 空 DataFrame
- 3 个 get_*_statement 端到端（mock 返回）

**B. `test_tri_channel_cf.py`** — 用 Job 1/3 fixture CSV
- `extract_tushare_year_values()` 用 mock provider
- `tri_match()` 用 tushare fixture vs RDS standard
- 分类逻辑（与 dual_channel 共享 classify_diff）

**C. `test_tushare_provider_live.py`**（拿到 token 后）
- 1 只股 × 1 年 smoke test
- 缺失 token 时 `pytest.skip`（不阻断 CI）

---

## 4. 文件结构

### 4.1 新增
```
astock_fundamentals/sources/api/tushare_provider.py    # 完整实现（替换 48 行 TODO 骨架）
scripts/tri_channel_cf_lib.py                          # 提取 + 对比工具
scripts/tri_channel_cf_download.py                     # CLI 入口
scripts/download_tushare_full.py                        # 5K 全量拉取
tests/test_tushare_provider.py                         # mock + 单元测试
tests/test_tri_channel_cf.py                            # 对比逻辑测试
data/exports_v2/cash_flow_tri_channel/                  # 输出目录（自动创建）
.env.tushare.example                                   # TOKEN 配置模板
docs/audit/2026-06-12-tushare-vs-rds-baseline.md       # 最终对比报告
docs/audit/2026-06-12-tushare-full-pull-summary.md     # 5K 拉取摘要（拿到 token 后写）
```

### 4.2 修改
```
astock_fundamentals/sources/api/__init__.py            # 导出 TushareProvider
pyproject.toml                                         # 加 tushare>=1.4 依赖
```

---

## 5. 限流 + 错误处理

### 5.1 限流实现
- 全局 `_last_call_ts` 跟踪最后一次 API 调用
- `_throttle()` 在每次 `_fetch()` 前调用，确保 ≥ 0.4s 间隔
- 默认 `rate_limit_sleep=0.4`，对应 ~150 req/min（远低于 200 上限，留安全余量）

### 5.2 错误分类
| 错误 | 处理 |
|------|------|
| ImportError | 立即抛，提示 `pip install tushare` |
| token 空 | 立即抛，提示 `--env-token` 或环境变量 |
| 权限/积分不足 | 不重试，标记 + 写日志 |
| 403 限流 | 5s 退避 + 重试 1 次，失败标记 |
| 网络超时 | 3 次指数退避（2/4/8s） |
| 空 DataFrame | 标 NO_DATA（报告期未发布） |
| 股票不存在 | 不重试，标记 + 继续 |

### 5.3 运行摘要
每只股处理结果记入 `_run_summary_*.json`：
```json
{
  "stock": "600519",
  "year": 2020,
  "status": "OK|NO_DATA|TOKEN_ERROR|403_RATE_LIMIT|EXCEPTION",
  "tushare_counts": {"exact": 35, "large_error": 3, ...},
  "rds_only_count": 12,
  "tushare_only_count": 4,
  "error": "..."  (optional)
}
```

---

## 6. 验证策略

### 6.1 vs RDS 对比（源头=巨潮资讯）
- 抽取 5-10 只股 × 多年份 × 3 表
- 复用 `RdsLoader.load_stock_data_tidy(stock, year, statement_type)` 加载 RDS
- 复用 `tri_match()` 做逐项对比
- 报告 HTML 高亮：
  - 🟢 exact（值匹配，0.01 元内）
  - 🟡 sub_yuan（差异 < 1 元）
  - 🟠 rounded（相对误差 < 1%，可能是精度差异）
  - 🔴 large_error（差异 > 1 元 or rel > 1%）
  - ⚪ no_match（tushare 没提供此项）

### 6.2 验证假设"源头=巨潮资讯"
预期：如果假设成立，对比结果应该与 RDS（也是巨潮资讯）有较高 exact_rate（>80%）。
- 若 exact_rate < 50%：假设不成立，可能 Tushare 是第三方转载
- 若 exact_rate > 80%：假设成立，Tushare 数据可信

### 6.3 5,000 只全量拉取
- 5,000 只 × 1 年 × 3 接口 = 15,000 次请求（仅年报）
- sleep 0.4s → 6,000s = 100 分钟 ≈ 1.7 小时
- sleep 0.4s × 0.4s = 5,000 × 0.4 × 3 接口 = 6,000 秒 = 1.7 小时
- 远低于 100,000/天日上限

---

## 7. 端到端测试流

1. **单元测试**（无 token）：
   ```bash
   pytest tests/test_tushare_provider.py tests/test_tri_channel_cf.py -v
   ```
   全部 PASS（mock）

2. **live smoke test**（需 token）：
   ```bash
   export TUSHARE_TOKEN=<user-provided>
   pytest tests/test_tushare_provider_live.py -v
   ```
   1 只股 × 1 年 = 3 次请求，验证 token 有效 + 字段非空

3. **小批量对比**（需 token）：
   ```bash
   echo "600519\n000651\n300750\n600036" > /tmp/stocks.txt
   python scripts/tri_channel_cf_download.py --stocks-file /tmp/stocks.txt --year 2020
   ```
   4 只股 × 1 年 × 3 表 = 12 次请求 + 12 次 RDS 加载

4. **5K 全量拉取**（需 token + 一次性时间）：
   ```bash
   python scripts/download_tushare_full.py --years 2020-2022 --resume
   ```
   5,000 × 3 × 3 = 45,000 次（3 年 3 表），约 5 小时

---

## 8. 文档交付

实施完成后产出 2 个文档：
1. **`docs/audit/2026-06-12-tushare-vs-rds-baseline.md`** — 5-10 只股对比结果
2. **`docs/audit/2026-06-12-tushare-full-pull-summary.md`** — 5K 全量拉取摘要

---

## 9. 不在范围内（YAGNI）

- ❌ 财务比率/估值指标（如 ROE/PB/PE）：本任务只做三表
- ❌ 实时行情/分笔数据：tushare 有这些接口但本任务不用
- ❌ 旧版本字段名兼容（task 1.5 sign-convention 别名）：如果遇到再做
- ❌ Wind/同花顺：tushare 是任务边界
- ❌ CI 自动化 5K 拉取：手动触发

---

## 10. 风险与决策记录

| 风险 | 缓解 |
|------|------|
| Token 失效 | 启动立即检测，错误信息清晰 |
| 5K 拉取超时 | 断点续传 + 可中断 + 可从断点恢复 |
| 字段名变化（RDS vs tushare） | tri_match 通过 best_match 模糊匹配 |
| Tushare 改名接口 | 集中在 `_fetch()` 一处，变更面小 |
| 限流 403 | 严格 sleep 0.4 + 退避重试 |
| 测试依赖 tushare 库 | mock 测试 + 真实测试 skip-on-no-token 双轨 |
