# Sina vs RDS 数据对比总结

## 1. 数据概况

### 对比范围
- **股票数量**: 100 只（前100只重叠股票）
- **年份范围**: 2000-2021年
- **对比组合**: 1430个（股票×年份×报表类型）
- **数据源**:
  - RDS: cninfo数据库（4836只股票，1991-2022年）
  - 新浪财经: 通过AKShare下载（3254只股票）

### 重叠范围
- **RDS股票**: 4836只
- **Sina股票**: 3254只
- **重叠股票**: 3253只（99.97%重叠率）

---

## 2. 总体对比结果

### 2.1 按报表类型

| 报表类型 | 对比数 | 匹配科目 | 匹配率 | 缺失数 | 未匹配数 |
|---------|--------|----------|--------|--------|----------|
| 资产负债表 | 515 | 16,761 | **83.7%** | 3,257 | 9,113 |
| 利润表 | 494 | 9,118 | **86.3%** | 1,451 | 2,850 |
| 现金流量表 | 381 | 10,552 | **63.6%** | 6,043 | 1,668 |
| **合计** | **1,390** | **36,431** | **77.7%** | **10,751** | **13,631** |

### 2.2 按年份趋势

| 年份 | 匹配率 | 说明 |
|------|--------|------|
| 2000-2002 | 62-70% | 较低，早期格式不规范 |
| 2003-2005 | 80-81% | 格式逐步规范化 |
| 2006-2020 | 76-87% | 相对稳定 |
| 2021 | 73.8% | 部分数据缺失 |

### 2.3 值准确率

- **平均值准确率**: 0.777
- **资产负债表**: 72.5-76.7%
- **利润表**: 更高（具体数据待分析）
- **现金流量表**: 较低（具体数据待分析）

---

## 3. 主要问题与规则

### 3.1 已发现的模式

#### (1) 命名差异模式

**Sina 与 RDS 的常见命名差异：**

| 类型 | Sina格式 | RDS格式 | 示例 |
|------|---------|---------|------|
| 前缀差异 | 无 | "其中：" | 营业收入 vs 其中：营业收入 |
| 后缀差异 | "(合计)" | 无 | 应收票据(合计) vs 应收票据 |
| 简称差异 | 完整名 | 简称 | 资产负债表 vs 负债表 |

#### (2) 数值匹配策略

**基于数值的匹配规则：**

```python
# 规则1: 值全等匹配
if abs(rds_value - sina_value) < 0.01:  # 值精确相等
    # 标记为同一科目，无论名称差异

# 规则2: 值近似匹配 (允许0.1%误差)
if abs(rds_value - sina_value) / max(abs(rds_value), abs(sina_value)) < 0.001:
    # 标记为可能同一科目，需要进一步验证
```

#### (3) 行业特定规则

**金融行业特殊处理：**
- 银行/保险的资产负债表科目更多
- 现金流量表结构更复杂
- 需要更宽松的匹配阈值

### 3.2 优化后的匹配策略

#### 优先级1: 精确名称匹配 (最高置信度)
```python
if normalize(rds_name) == normalize(sina_name):
    return "exact"
```

#### 优先级2: 别名匹配 (使用 aliases.yaml)
```python
aliases = load_aliases(statement_type)
for standard, variants in aliases.items():
    if normalize(sina_name) in [normalize(v) for v in variants]:
        return "alias"
```

#### 优先级3: 价值链匹配 (中置信度)
```python
if abs(rds_value - sina_value) / max(abs(rds_value), abs(sina_value)) < 0.001:
    return "value_match"
```

#### 优先级4: 模糊匹配 (最低置信度)
```python
similarity = calculate_similarity(rds_name, sina_name)
if similarity > 0.8:
    return "fuzzy"
```

---

## 4. 改进建议

### 4.1 别名映射更新

基于对比结果，建议更新 `rules/value_mapping_rules.yaml`：

1. 添加更多RDS→Sina的名称映射
2. 处理金融行业的特殊科目
3. 统一"其中："前缀的处理

### 4.2 匹配阈值调整

| 报表类型 | 建议阈值 | 说明 |
|---------|----------|------|
| 资产负债表 | 0.8% | 严格匹配，确保平衡表恒等式 |
| 利润表 | 0.5% | 较严格，确保利润准确性 |
| 现金流量表 | 1.0% | 相对宽松，部分科目口径差异较大 |

### 4.3 数据质量评估

建议为每个匹配结果增加：
- **置信度评分**: 基于名称相似度+数值匹配度
- **来源标记**: 标记数据来自RDS还是Sina
- **差异原因**: 如果值不匹配，记录可能原因

---

## 5. 代码实现建议

### 5.1 改进compare_stock函数

```python
def compare_stock_optimized(rds_data, sina_data, aliases, ...):
    # 1. 先进行名称匹配
    matched = name_match(rds_data, sina_data, aliases)
    
    # 2. 对未匹配的项进行数值匹配
    unmatched_rds = set(rds_data.keys()) - set(matched.values())
    unmatched_sina = set(sina_data.keys()) - set(matched.keys())
    
    for rds_name in unmatched_rds:
        for sina_name in unmatched_sina:
            if value_match(rds_data[rds_name], sina_data[sina_name]):
                matched[rds_name] = sina_name
    
    # 3. 输出结果
    return matched
```

### 5.2 规则存储

建议将规则存储为JSON格式，便于版本控制：

```json
{
  "version": "1.0",
  "updated_at": "2026-01-01",
  "rules": {
    "name_mapping": { ... },
    "value_thresholds": { ... },
    "industry_rules": { ... }
  }
}
```

---

## 6. 下一步行动

1. **更新rules/value_mapping_rules.yaml**
   - 添加3253只股票的对比结果
   - 统一金融行业特殊科目
   - 添加年份特定规则（1990s格式差异）

2. **优化compare_stock函数**
   - 实现四优先级匹配策略
   - 添加置信度评分
   - 支持增量学习

3. **扩展数据范围**
   - 下载剩余1583只RDS股票的Sina数据
   - 对比更多年份的数据
   - 建立自动化对比管道

---

**报告生成时间**: 2026-05-30
**数据来源**: Sina (3254 stocks) + RDS (4836 stocks)
**对比结果**: 36,431 matched / 46,793 total = 77.7%
