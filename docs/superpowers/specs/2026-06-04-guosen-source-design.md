# 国信证券数据源集成 设计文档

**日期**: 2026-06-04
**状态**: 设计阶段 (待用户审阅)
**关联**: [[2026-06-04-sina-rds-cleaning-pipeline-design]]

---

## 1. 目标

将国信证券 (Guosen) `gs-stock-financial-query` skill 集成为项目的**第三个独立数据源**，与现有 `sources/api/akshare_provider.py` (Sina) 平行。

**支持**: A股 + 港股 的资产负债表/利润表/现金流量表
**接入方式**: 调用国信 skill 的 `get_data.py` 脚本（已下载到本地），通过 API key 鉴权

---

## 2. 现有结构

```
astock_fundamentals/sources/
├── api/                    # 已有 akshare/tushare/wind providers (骨架)
│   ├── __init__.py
│   ├── akshare_provider.py # AKShareProvider class
│   ├── tushare_provider.py # TushareProvider class
│   └── wind_provider.py    # WindProvider class
├── rds/                    # RDS (cninfo) 加载器
└── pdf/                    # PDF 解析
```

**国信数据源定位**: `astock_fundamentals/sources/guosen/` (与 api/ 平行)

---

## 3. 设计

### 3.1 目录与文件

```
astock_fundamentals/sources/guosen/
├── __init__.py            # 导出 GuosenLoader
├── guosen_loader.py       # 核心: GuosenLoader 类
├── gs_skill/              # 国信 skill 源码副本 (避免依赖 .claude/skills)
│   ├── SKILL.md
│   └── scripts/
│       └── get_data.py     # 国信官方 skill 脚本 (不变)
├── README.md              # API Key 配置 + 用法
└── .env.example           # GS_API_KEY= 模板
```

**与 .claude/skills/guosen-financial/ 关系**:
- 不安装为 Claude Code skill plugin (那是 agent 层面)
- 本项目只用其 `get_data.py` 脚本作为 HTTP client 库
- 项目内副本保证版本固定 + 可独立测试

### 3.2 GuosenLoader 接口

与 SinaLoader 对称，便于 baseline/pipeline 切换数据源：

```python
class GuosenLoader:
    def __init__(self, api_key: Optional[str] = None):
        """api_key: 优先参数, 其次 GS_API_KEY env, 其次 ./memory.md"""
    
    def read_statement(self, stock_code: str, statement_type: str) -> pd.DataFrame:
        """单期单表读取. statement_type: balance_sheet/income_statement/cash_flow"""
    
    def get_annual(
        self, stock_code: str, target_years: List[int], statement_type: str,
    ) -> pd.DataFrame:
        """多年度切片. stock_code: 6位代码 (国信内部判断 SH/SZ)"""
    
    def health_check(self) -> bool:
        """验证 API key + 网络连通性"""
```

### 3.3 与 SinaLoader 的关键差异

| 维度 | SinaLoader | GuosenLoader |
|------|------------|--------------|
| 数据来源 | 本地 CSV (`data/akshare_bulk/`) | 国信 HTTP API |
| 网络依赖 | 无 | 必需 |
| 鉴权 | 无 | `GS_API_KEY` env |
| 港股 | ❌ | ✅ |
| 数据范围 | 2000+ 股票 1989-2026+ | 视 API 配额 |
| 调用模式 | 拉 (按需读 CSV) | 推 (按需 HTTP) |

### 3.4 数据格式对齐

国信返回 JSON 格式 `{result: {code, msg}, data: {info: [...], ...}}`。
- `info` 数组含 `{key, name, value}` 结构
- 字段名多为中文 (类似 Sina)
- 推测**国信字段名 ≈ Sina 字段名** (同源于中国会计准则)

→ **不需要新写 aliases**，可复用 `rules/aliases.yaml` 现有规则

### 3.5 Pipeline 集成

`scripts/clean_sina_pipeline.py` 加 `--source` 参数:

```bash
# Sina (现有)
python scripts/clean_sina_pipeline.py --source sina --stocks 000001 --years 2019 2020

# Guosen (新)
python scripts/clean_sina_pipeline.py --source guosen --stocks 000001 --years 2019 2020

# 港股 (新)
python scripts/clean_sina_pipeline.py --source guosen --stocks 02020 --years 2020
```

底层用同一 `rule_cleaner.py` 做清洗 — 通用化。

### 3.6 Baseline 集成

`scripts/baseline_2019_2022.py` 加 `--source` 参数:

```bash
python scripts/baseline_2019_2022.py --source guosen
# 跑国信 vs RDS baseline 对比
```

→ **首次跑将验证国信字段名与 Sina 是否一致**。如果不一致，自动学习出 `sina_to_gs` 规则块。

### 3.7 错误处理

- **API key 缺失**: raise `GuosenAuthError` with hint
- **HTTP 错误**: return `{"error": "..."}` 包装, 上层决定 retry
- **数据为空**: 抛 `GuosenEmptyDataError`, 跳过并记录到 gap report
- **网络超时**: 重试 2 次 (15s × 2), then give up

### 3.8 测试策略

- **Unit tests**: mock `urllib.request.urlopen` 返回固定 JSON
- **Integration test**: 用 mock API key 跑 `health_check`
- **E2E test**: 不跑真实 API (避免消耗配额), 改测 loader 的字段映射 + 错误传播

---

## 4. 文件变更

### 新增

| 文件 | 行数估计 | 用途 |
|------|---------|------|
| `astock_fundamentals/sources/guosen/__init__.py` | 5 | 导出 GuosenLoader |
| `astock_fundamentals/sources/guosen/guosen_loader.py` | 200 | 核心加载器 |
| `astock_fundamentals/sources/guosen/README.md` | 60 | 用法 |
| `astock_fundamentals/sources/guosen/.env.example` | 3 | API key 模板 |
| `astock_fundamentals/sources/guosen/gs_skill/scripts/get_data.py` | (副本) | 国信官方脚本 |
| `astock_fundamentals/sources/guosen/gs_skill/SKILL.md` | (副本) | 国信官方文档 |
| `tests/ground_truth/test_guosen_loader.py` | 150 | 单元测试 |
| `tests/ground_truth/test_guosen_smoke.py` | 30 | API key 健康检查 (skip if no key) |

### 修改

| 文件 | 改动 |
|------|------|
| `scripts/clean_sina_pipeline.py` | 加 `--source sina|guosen` 参数 |
| `scripts/baseline_2019_2022.py` | 加 `--source` 参数 + source-aware 缓存路径 |

### 不变

- `rules/aliases.yaml` — 国信字段名预期与 Sina 一致
- `astock_fundamentals/ground_truth/rule_cleaner.py` — 通用
- `astock_fundamentals/ground_truth/comparator.py` — 通用

---

## 5. 实施优先级

1. **P0**: 创建 `sources/guosen/` 目录结构 + 复制 skill 脚本 (本日)
2. **P0**: 实现 `GuosenLoader` 类 + 单元测试 (本日)
3. **P1**: pipeline/baseline 加 `--source` 参数 (本日)
4. **P2**: 港股支持 (下轮)
5. **P3**: 三源对比自动学习 (后续)

---

## 6. 待确认

- [x] 国信数据源位置: `astock_fundamentals/sources/guosen/` (与 api/ 平行)
- [x] API key 加载优先级: 参数 > env > `./memory.md`
- [x] 港股是否在 P0 范围: 包含, 但仅作为字段映射测试, 不做完整 baseline
- [x] skill 脚本副本: 放 `sources/guosen/gs_skill/scripts/get_data.py` (避免项目根污染)
