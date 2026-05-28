# Tidy Data Pipeline 设计方案

> **日期**: 2026-05-28
> **目标**: 将 PDF 提取数据转化为规范的 Tidy Data 格式，与 RDS 数据库完全对齐，实现 100% 准确识别

---

## 1. 背景问题

### 1.1 同名指标冲突

在财务三大表中，同一中文指标名可能出现在不同大项目下，金额完全不同：

| 字段代码 | 中文名称 | 值 | 所属大项目 |
|---------|---------|-----|-----------|
| F033N | 利息收入 | 3,077,859,584.49 | 营业总收入 |
| F063N | 利息收入 | 278,697,733.32 | 营业总成本 |

现有 `ITEM_ALIAS_MAP` 只按中文名称映射，无法区分这两个同名指标。

### 1.2 展示顺序丢失

PDF 提取结果没有保留原报表的展示顺序，导致与 RDS 数据的对齐无法按顺序验证。

### 1.3 别名匹配精度不足

现有 `aliases.yaml` 是扁平结构，未区分行业和报告期类型，导致跨行业匹配时出现误匹配。

---

## 2. 目标

1. **数据结构**：采用 Tidy Data 格式，以 `item_code + item_name` 作为指标唯一标识
2. **展示顺序**：按 RDS 数据库中的字段顺序输出，保持与标准报表一致
3. **别名分层**：`aliases.yaml` 按行业 × 报告期类型组织，提升匹配精度
4. **验证机制**：每份 PDF 提取后立即与 RDS 全字段对比，100% 匹配才算达标

---

## 3. 数据结构设计

### 3.1 Tidy Data 格式

每条记录代表一个指标值：

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | string | 股票代码，如 "600519" |
| report_year | int | 报告年份，如 2020 |
| report_type | string | 报告类型：annual / half_year / quarter_q1 / quarter_q3 |
| statement_type | string | 报表类型：income_statement / balance_sheet / cash_flow |
| item_code | string | RDS 字段代码，如 "F033N" |
| item_name | string | 中文指标名称，如 "利息收入" |
| value | float | 数值（元） |
| display_order | int | 在报表中的展示顺序（从 RDS 获取） |

### 3.2 display_order 获取

RDS 数据本身没有显式的顺序字段。display_order 通过以下方式获取：

1. 从 `decode_mappings_by_type.json` 中硬编码顺序（字段代码的字典序或人工排定的顺序）
2. 或从 RDS 原始列顺序推断（F001N → F002N → ...）

建议方案：在 `decode_mappings_by_type.json` 中，每个 statement_type 的字段按展示顺序排列，display_order 即为其在 JSON 对象中的索引位置。

---

## 4. 别名分层设计

### 4.1 现有结构问题

当前 `aliases.yaml` 是扁平结构：

```yaml
利息收入: [利息收入, ...]
```

### 4.2 目标结构

按行业 × 报告期类型分层：

```yaml
# 按报告期类型区分
annual:
  default:
    利息收入: [利息收入, ...]
  银行:
    利息收入: [利息收入, 利息收入(银行口径), ...]

half_year:
  default:
    利息收入: [利息收入, ...]
  银行:
    利息收入: [利息收入, ...]

quarter_q1:
  default:
    利息收入: [利息收入, ...]
```

### 4.3 匹配优先级

1. 先精确匹配：行业 + 报告期类型 + 指标名
2. 再模糊匹配：报告期类型 + 指标名
3. 最后兜底：default + 指标名

---

## 5. 核心模块设计

### 5.1 RdsLoader 增强

**文件**: `extraction/ground_truth/rds_loader.py`

**改动**:

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
```

**display_order 来源**: 在 `decode_mappings_by_type.json` 中，每个 statement_type 的字段按展示顺序排列。

### 5.2 ItemMapper 增强

**文件**: `extraction/ground_truth/mapper.py`

**改动**:

- 增加行业和报告期类型参数
- 使用分层别名进行匹配
- 输出 Tidy Data 格式

### 5.3 Comparator 增强

**文件**: `extraction/ground_truth/comparator.py`

**改动**:

- 全字段逐项对比（不只看 matched rate）
- 输出详细的差异报告
- 标记未匹配的字段别名，提示需要补充到 aliases.yaml

---

## 6. aliases.yaml 重构

### 6.1 迁移步骤

1. **备份**现有的扁平结构到 `aliases_flat.yaml`
2. **创建**新的分层结构 `aliases_v2.yaml`
3. **迁移**现有规则到 `default` 分组
4. **补充**各行业的特定规则

### 6.2 字段顺序定义

在 `decode_mappings_by_type.json` 中，字段已按展示顺序排列。display_order 即为字段在 JSON 对象中的位置（0-based index）。

```json
{
  "income_statement": {
    "F035N": "一、营业总收入",    // order=0
    "F006N": "其中：营业收入",    // order=1
    "F033N": "利息收入",          // order=2
    ...
  }
}
```

---

## 7. 对比验证流程

### 7.1 逐文件验证

```
PDF 提取 → 别名归一化 → Tidy Data 转换 → RDS 对比 → 差异报告
```

### 7.2 验证指标

| 指标 | 说明 | 达标阈值 |
|------|------|---------|
| field_match_rate | 字段级匹配率 | 100% |
| value_match_rate | 数值级匹配率 | 100% |
| order_match_rate | 顺序匹配率 | 100% |

### 7.3 差异分类

| 类型 | 说明 | 处理 |
|------|------|------|
| MISSING | PDF提取缺少该字段 | 补充别名规则或修复提取逻辑 |
| UNMATCHED | RDS有但PDF无该名称 | 补充别名映射 |
| VALUE_DIFF | 字段名匹配但值不同 | 检查单位或提取错误 |
| ORDER_DIFF | 顺序不一致 | 调整 display_order |

---

## 8. 文件结构

```
extraction/
├── ground_truth/
│   ├── rds_loader.py      # 增强：load_stock_data_tidy()
│   ├── mapper.py          # 增强：分层别名匹配
│   ├── comparator.py      # 增强：Tidy Data 对比
│   └── gap_analyzer.py    # 增强：差异分类 + 别名建议
├── config.py              # 别名加载支持分层结构
└── parsers/
    └── table_parser.py    # 可能需要调整：支持 display_order 输出

rules/
├── aliases.yaml           # 重构：分层结构 aliases_v2.yaml
├── aliases_flat.yaml     # 备份：现有扁平结构
└── field_order.yaml       # 新增：按 statement_type 的字段展示顺序
```

---

## 9. 实施阶段

### Phase 1: 基础设施（1-2天）

- [ ] 创建 `decode_mappings_by_type.json` 的字段顺序索引
- [ ] 创建 `field_order.yaml` 定义各报表的展示顺序
- [ ] 增强 `RdsLoader.load_stock_data_tidy()` 返回 Tidy Data
- [ ] 创建 `aliases_v2.yaml` 分层结构（迁移现有规则）

### Phase 2: 别名分层（2-3天）

- [ ] 修改 `config.py` 支持分层别名加载
- [ ] 修改 `mapper.py` 支持行业 × 报告期类型匹配
- [ ] 批量对比验证，分析缺失别名

### Phase 3: 全量验证（持续）

- [ ] 增强 `Comparator` 输出详细差异报告
- [ ] `GapAnalyzer` 根据差异自动建议新别名
- [ ] 建立别名补充流程

### Phase 4: PDF 下载扩展（按需）

- [ ] 确定 2022 年前各股票需补充的年报/半年报/季报
- [ ] 批量下载并提取
- [ ] 持续对比验证

---

## 10. 关键决策

1. **display_order 来源**: 从 `decode_mappings_by_type.json` 的字段顺序推断，不修改 RDS 原始数据
2. **Tidy Data 存储格式**: SQLite 表，每条记录一个指标值
3. **别名分层粒度**: 行业 × 报告期类型两级
4. **达标标准**: 字段匹配率 = 100% 且 数值匹配率 = 100%

---

## 11. 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 部分历史 PDF 无法下载 | 中 | 中 | 分阶段验证，记录缺失数据 |
| 同名指标数量超出预期 | 低 | 高 | item_code 唯一标识，设计已覆盖 |
| 别名规则爆炸性增长 | 中 | 低 | 分层 + 分行业控制，避免扁平膨胀 |
