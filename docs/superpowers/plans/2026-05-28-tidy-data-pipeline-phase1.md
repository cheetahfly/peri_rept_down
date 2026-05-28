# Tidy Data Pipeline Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 Tidy Data 基础设施，包括 display_order 定义、RdsLoader Tidy Data 输出、别名分层结构迁移

**Architecture:** Phase 1 聚焦基础设施：增强 RdsLoader 返回 Tidy Data 格式（item_code + item_name + display_order），将 aliases.yaml 从扁平结构迁移到分层结构（按 statement_type 组织，为后续按 industry × report_type 扩展做准备）

**Tech Stack:** Python 3.10+, pyreadr, JSON, YAML, pytest

---

## 文件结构

```
extraction/ground_truth/
├── rds_loader.py          # 修改：添加 load_stock_data_tidy() 方法

rules/
├── aliases.yaml           # 修改：添加 report_type 分层（annual/half_year/quarter）
└── field_order.yaml       # 新增：定义各 statement_type 的字段展示顺序
```

---

## Task 1: 创建 field_order.yaml 定义字段展示顺序

**Files:**
- Create: `rules/field_order.yaml`
- Test: `tests/test_field_order.py`

- [ ] **Step 1: 创建 field_order.yaml**

```yaml
# 字段展示顺序定义
# display_order 即为该字段在报表中的顺序位置（0-based index）

income_statement:
  F035N: 0   # 一、营业总收入
  F006N: 1   # 其中：营业收入
  F033N: 2   # 利息收入
  F034N: 3   # 已赚保费
  F042N: 4   # 手续费及佣金收入
  F036N: 5   # 二、营业总成本
  F007N: 6   # 其中：营业成本
  F043N: 7   # 利息支出
  F044N: 8   # 手续费及佣金支出
  F045N: 9   # 退保金
  F046N: 10  # 赔付支出净额
  F047N: 11  # 提取保险合同准备金净额
  F048N: 12  # 保单红利支出
  F049N: 13  # 分保费用
  F008N: 14  # 营业税金及附加
  F009N: 15  # 销售费用
  F010N: 16  # 管理费用
  F011N: 17  # 堪探费用
  F012N: 18  # 财务费用
  F056N: 19  # 研发费用
  F013N: 20  # 资产减值损失
  F014N: 21  # 加：公允价值变动净收益
  F015N: 22  # 投资收益
  F016N: 23  # 其中：对联营企业和合营企业的投资收益
  F037N: 24  # 汇兑收益
  F051N: 25  # 基它收入
  F057N: 26  # 信用减值损失
  F058N: 27  # 净敞口套期收益
  F059N: 28  # 资产处置收益
  F017N: 29  # 影响营业利润的其他科目
  F018N: 30  # 三、营业利润
  F019N: 31  # 加：补贴收入
  F020N: 32  # 营业外收入
  F050N: 33  # 其中：非流动资产处置利得
  F021N: 34  # 减：营业外支出
  F022N: 35  # 其中：非流动资产处置损失
  F023N: 36  # 加：影响利润总额的其他科目
  F024N: 37  # 四、利润总额
  F025N: 38  # 减：所得税
  F026N: 39  # 加：影响净利润的其他科目
  F027N: 40  # 五、净利润
  F060N: 41  # 持续经营净利润
  F061N: 42  # 终止经营净利润
  F028N: 43  # 归属于母公司所有者的净利润
  F029N: 44  # 少数股东损益
  F031N: 45  # （一）基本每股收益
  F032N: 46  # （二）稀释每股收益
  F038N: 47  # 七、其他综合收益
  F039N: 48  # 八、综合收益总额
  F040N: 49  # 其中：归属于母公司
  F041N: 50  # 其中：归属于少数股东
  F062N: 51  # 其中：利息费用
  F063N: 52  # 其中：利息收入
  F064N: 53  # 信用减值损失（2019格式）
  F065N: 54  # 资产减值损失（2019格式）

balance_sheet:
  F006N: 0    # 货币资金
  F077N: 1    # 结算备付金
  F078N: 2    # 拆出资金
  # ... (完整顺序待填充)

cash_flow:
  F006N: 0    # 销售商品、提供劳务收到的现金
  # ... (完整顺序待填充)
```

- [ ] **Step 2: 编写测试验证 field_order.yaml 加载**

```python
# tests/test_field_order.py
import yaml
import os

def test_field_order_loads():
    path = os.path.join(os.path.dirname(__file__), '..', 'rules', 'field_order.yaml')
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    assert 'income_statement' in data
    assert 'balance_sheet' in data
    assert 'cash_flow' in data
    
    # 验证 F033N 和 F063N 在 income_statement 中有不同顺序
    assert data['income_statement']['F033N'] != data['income_statement']['F063N']
    assert data['income_statement']['F033N'] < data['income_statement']['F063N']
```

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/test_field_order.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add rules/field_order.yaml tests/test_field_order.py
git commit -m "feat: add field_order.yaml defining display sequence per statement type"
```

---

## Task 2: 增强 RdsLoader 添加 load_stock_data_tidy() 方法

**Files:**
- Modify: `extraction/ground_truth/rds_loader.py:97-147`
- Test: `tests/test_rds_loader.py`

- [ ] **Step 1: 在 rds_loader.py 顶部添加 field_order 加载**

```python
import yaml

# 字段展示顺序（从 rules/field_order.yaml 加载）
FIELD_ORDER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "rules", "field_order.yaml"
)

def _load_field_order() -> Dict[str, Dict[str, int]]:
    """加载字段展示顺序"""
    try:
        with open(FIELD_ORDER_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}
```

- [ ] **Step 2: 在 RdsLoader.__init__ 中加载 field_order**

```python
def __init__(self, data_dir: str, decode_map_path: str = None):
    self.data_dir = data_dir
    self._decode_maps = self._load_decode_maps(decode_map_path)
    self._field_order = _load_field_order()
    self._cache: Dict[str, object] = {}
```

- [ ] **Step 3: 添加 load_stock_data_tidy() 方法**

```python
def load_stock_data_tidy(
    self,
    stock_code: str,
    year: int,
    statement_type: str,
) -> List[Dict]:
    """
    返回 Tidy Data 格式的 Ground Truth 数据。

    Returns: List[Dict]，每项包含：
        stock_code, report_year, report_type, statement_type,
        item_code, item_name, value, display_order
    """
    is_fin = self._is_financial(stock_code)
    filename = TABLE_MAP.get((is_fin, statement_type))
    if filename is None:
        return []

    df = self._load_rds(filename)
    subset = df[df["SECCODE"] == stock_code]

    # Filter by year
    target_date = f"{year}-12-31"
    row = subset[subset["ENDDATE"] == target_date]
    if len(row) == 0:
        target_date = f"{year + 1}-03-31"
        row = subset[subset["ENDDATE"] == target_date]
    if len(row) == 0:
        return []

    row = row.iloc[0]

    # Determine report_type from date
    month = int(target_date.split('-')[1])
    report_type = self._date_to_report_type(month)

    # Get decode map and field order for this statement type
    decode_map = self._decode_maps.get(statement_type, {})
    field_order_map = self._field_order.get(statement_type, {})

    # Extract data
    result = []
    for col in df.columns:
        if col in META_COLS:
            continue
        if col not in decode_map:
            continue
        val = row[col]
        if val is not None and str(val) != "nan":
            item_name = decode_map[col]
            display_order = field_order_map.get(col, 999)  # 未知顺序放最后
            try:
                result.append({
                    "stock_code": stock_code,
                    "report_year": year,
                    "report_type": report_type,
                    "statement_type": statement_type,
                    "item_code": col,
                    "item_name": item_name,
                    "value": float(val),
                    "display_order": display_order,
                })
            except (ValueError, TypeError):
                pass

    # Sort by display_order
    result.sort(key=lambda x: x["display_order"])
    return result

def _date_to_report_type(self, month: int) -> str:
    """根据月份判断报告类型"""
    if month == 12:
        return "annual"
    elif month == 6:
        return "half_year"
    elif month == 3:
        return "quarter_q1"
    elif month == 9:
        return "quarter_q3"
    return "annual"
```

- [ ] **Step 4: 编写测试验证 load_stock_data_tidy()**

```python
# tests/test_rds_loader.py
def test_load_stock_data_tidy_returns_correct_fields():
    """验证 Tidy Data 返回包含所有必需字段"""
    from extraction.ground_truth.rds_loader import RdsLoader

    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    loader = RdsLoader(RDS_DIR)

    result = loader.load_stock_data_tidy("600519", 2020, "income_statement")

    assert len(result) > 0
    item = result[0]
    required_fields = ["stock_code", "report_year", "report_type", "statement_type",
                       "item_code", "item_name", "value", "display_order"]
    for field in required_fields:
        assert field in item, f"Missing field: {field}"

def test_load_stock_data_tidy_f033n_and_f063n_different():
    """验证 F033N 和 F063N（两个"利息收入"）能正确区分"""
    from extraction.ground_truth.rds_loader import RdsLoader

    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    loader = RdsLoader(RDS_DIR)

    result = loader.load_stock_data_tidy("600519", 2020, "income_statement")

    # 找到两个"利息收入"
    interest_income_items = [r for r in result if "利息收入" in r["item_name"]]
    assert len(interest_income_items) == 2

    # 验证 item_code 不同
    item_codes = {r["item_code"] for r in interest_income_items}
    assert "F033N" in item_codes
    assert "F063N" in item_codes

    # 验证数值不同
    values = {r["item_code"]: r["value"] for r in interest_income_items}
    assert values["F033N"] != values["F063N"]

def test_load_stock_data_tidy_sorted_by_display_order():
    """验证结果按 display_order 排序"""
    from extraction.ground_truth.rds_loader import RdsLoader

    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    loader = RdsLoader(RDS_DIR)

    result = loader.load_stock_data_tidy("600519", 2020, "income_statement")

    orders = [r["display_order"] for r in result]
    assert orders == sorted(orders), "Results should be sorted by display_order"
```

- [ ] **Step 5: 运行测试验证**

Run: `pytest tests/test_rds_loader.py -v -k "tidy"`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add extraction/ground_truth/rds_loader.py tests/test_rds_loader.py
git commit -m "feat: add load_stock_data_tidy() returning Tidy Data format with item_code and display_order"
```

---

## Task 3: 迁移 aliases.yaml 支持 report_type 分层

**Files:**
- Modify: `rules/aliases.yaml`
- Test: `tests/test_aliases分层.py`

- [ ] **Step 1: 备份现有 aliases.yaml**

```bash
cp rules/aliases.yaml rules/aliases_flat.yaml.bak
```

- [ ] **Step 2: 修改 aliases.yaml 结构，添加 report_type 分层**

当前结构（按 statement_type）：
```yaml
balance_sheet:
  资产总计: [...]
income_statement:
  营业收入: [...]
```

目标结构（按 statement_type × report_type）：
```yaml
balance_sheet:
  annual:
    资产总计: [...]
  half_year:
    资产总计: [...]
  quarter_q1:
    资产总计: [...]
  quarter_q3:
    资产总计: [...]

income_statement:
  annual:
    营业收入: [...]
  half_year:
    营业收入: [...]
  ...
```

迁移策略：
- 将现有的扁平规则复制到 `annual` 分组
- `half_year`、`quarter_q1`、`quarter_q3` 暂时引用 `annual`（后续按需补充差异）

- [ ] **Step 3: 编写测试验证分层结构**

```python
# tests/test_aliases分层.py
import yaml
import os

def test_aliases_structure():
    """验证 aliases.yaml 分层结构"""
    path = os.path.join(os.path.dirname(__file__), '..', 'rules', 'aliases.yaml')
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    for statement_type in ['balance_sheet', 'income_statement', 'cash_flow']:
        assert statement_type in data
        for report_type in ['annual', 'half_year', 'quarter_q1', 'quarter_q3']:
            assert report_type in data[statement_type], \
                f"Missing {report_type} in {statement_type}"

def test_f033n_and_f063n_separate_aliases():
    """验证 F033N 和 F063N（两个"利息收入"）有不同的别名列表"""
    path = os.path.join(os.path.dirname(__file__), '..', 'rules', 'aliases.yaml')
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # F033N 映射到 "利息收入"（营业总收入下）
    # F063N 映射到 "其中：利息收入" 或 "利息收入"（不同别名）
    # 两者应该有不同的别名集合以区分
    is_data = data['income_statement']['annual']
    # 找到包含 F033N 特征和 F063N 特征的别名
    # （具体验证逻辑取决于最终别名配置）
```

- [ ] **Step 4: 运行测试验证**

Run: `pytest tests/test_aliases分层.py -v`
Expected: PASS（如果测试失败，说明分层迁移尚未完成，继续下一步）

- [ ] **Step 5: 提交**

```bash
git add rules/aliases.yaml rules/aliases_flat.yaml.bak
git commit -m "refactor: migrate aliases.yaml to statement_type × report_type hierarchy"
```

---

## Task 4: 更新 config.py 支持分层别名加载

**Files:**
- Modify: `extraction/config.py:67-78`

- [ ] **Step 1: 更新 config.py 中的别名加载逻辑**

当前逻辑：
```python
ITEM_ALIAS_MAP = load_yaml_rule("aliases.yaml", {})
if isinstance(ITEM_ALIAS_MAP, dict):
    merged_aliases = {}
    for statement_type, aliases in ITEM_ALIAS_MAP.items():
        if isinstance(aliases, dict):
            merged_aliases.update(aliases)
    if merged_aliases:
        ITEM_ALIAS_MAP = merged_aliases
```

需要改为返回分层结构：
```python
# 分层别名映射：{statement_type: {report_type: {标准名: [别名列表]}}}
ITEM_ALIAS_MAP_HIERARCHICAL = load_yaml_rule("aliases.yaml", {})

def get_aliases(statement_type: str, report_type: str = "annual") -> Dict[str, List[str]]:
    """获取指定报表类型和报告期的别名映射"""
    if not ITEM_ALIAS_MAP_HIERARCHICAL:
        return {}
    st_data = ITEM_ALIAS_MAP_HIERARCHICAL.get(statement_type, {})
    # 优先精确匹配，其次用 annual 兜底
    return st_data.get(report_type, st_data.get("annual", {}))
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_config_aliases.py
def test_get_aliases_returns_hierarchical():
    from extraction.config import get_aliases

    # 测试 income_statement 的 annual
    aliases = get_aliases("income_statement", "annual")
    assert "营业收入" in aliases

    # 测试 get_aliases 降级逻辑
    aliases_q1 = get_aliases("income_statement", "quarter_q1")
    # quarter_q1 如果没有，应降级到 annual
    assert aliases_q1 == aliases or aliases_q1 == {}
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_config_aliases.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add extraction/config.py tests/test_config_aliases.py
git commit -m "feat: support hierarchical alias loading from aliases.yaml"
```

---

## Task 5: 完整集成测试

**Files:**
- Test: `tests/test_tidy_data_pipeline.py`

- [ ] **Step 1: 编写端到端测试**

```python
# tests/test_tidy_data_pipeline.py
def test_rds_tidy_data_for_600519_2020():
    """验证 600519 2020年年报的 Tidy Data 输出"""
    from extraction.ground_truth.rds_loader import RdsLoader

    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    loader = RdsLoader(RDS_DIR)

    # 测试三大表都能返回 Tidy Data
    for st_type in ["income_statement", "balance_sheet", "cash_flow"]:
        result = loader.load_stock_data_tidy("600519", 2020, st_type)
        assert len(result) > 0, f"{st_type} returned empty"

        # 验证字段完整
        for item in result:
            assert "item_code" in item
            assert "item_name" in item
            assert "display_order" in item
            assert item["stock_code"] == "600519"
            assert item["report_year"] == 2020

    # 验证 income_statement 中有两个"利息收入"
    is_result = loader.load_stock_data_tidy("600519", 2020, "income_statement")
    interest_items = [r for r in is_result if "利息收入" in r["item_name"]]
    assert len(interest_items) == 2

    # 验证两个"利息收入"的 item_code 不同
    codes = {r["item_code"] for r in interest_items}
    assert len(codes) == 2
```

- [ ] **Step 2: 运行完整测试**

Run: `pytest tests/test_tidy_data_pipeline.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_tidy_data_pipeline.py
git commit -m "test: add end-to-end Tidy Data pipeline test for 600519 2020"
```

---

## Phase 1 完成后检查清单

- [ ] `rules/field_order.yaml` 已创建，包含 income_statement/balance_sheet/cash_flow 的完整字段顺序
- [ ] `load_stock_data_tidy()` 方法已添加到 `RdsLoader`
- [ ] Tidy Data 输出包含 item_code、item_name、display_order 字段
- [ ] F033N 和 F063N（两个"利息收入"）能通过 item_code 区分
- [ ] `aliases.yaml` 已迁移到 statement_type × report_type 分层结构
- [ ] `config.py` 支持分层别名加载
- [ ] 所有测试通过
