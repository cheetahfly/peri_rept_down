# 100%准确提取商业化系统设计

**日期**: 2026-05-11
**版本**: v1.0
**状态**: 已批准

## 1. 目标与约束

### 1.1 核心目标
- 实现**100%数值准确**的年报数据提取
- 形成**商业化**输出能力（JSON + 数据库双输出）
- 支持**CAS（中国企业会计准则）**标准科目映射

### 1.2 关键约束
- **数值精度**: 零容忍，与PDF原文完全一致
- **单位**: 统一转换为"元"
- **科目映射**: 原始名称 → CAS标准口径
- **自动化**: 全力尝试全自动化，边界情况标记待审

---

## 2. 系统架构

### 2.1 四层架构

```
┌────────────────────────────────────────────────────────────────────┐
│ Layer 1: 智能页面检测                                              │
│ - GlobalDensityScanner    全页密度扫描(非仅前20页)                  │
│ - CIDFontDetector         CID字体识别(阈值15%)                       │
│ - PageTypeClassifier     页面分类(目录/正文/附注/表格)             │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│ Layer 2: 多引擎提取 (级联Fallback)                                  │
│ - pdfplumber           正常PDF首选                                  │
│ - PyMuPDF             CID字体但可解码                                │
│ - pdf2htmlEX          复杂CID字体HTML转换                           │
│ - TesseractOCR       终极兜底                                      │
│      └─ EngineValidator   多引擎结果交叉验证                        │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│ Layer 3: 语义重建                                                  │
│ - TableStructureParser   表格解析(列对齐/跨页合并)                  │
│ - SemanticRecovery       科目名恢复(pdf2htmlEX+词汇推断+OCR)       │
│ - ChartOfAccountsMapper  CAS标准口径映射                           │
│      └─ UnitNormalizer     单位统一转换为元                         │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│ Layer 4: 质量门控 (零容忍验证)                                      │
│ - CompletenessValidator  勾稽关系校验(BS=IS期末结转)               │
│ - ReasonablenessChecker  合理值域检查                              │
│ - YoYConsistencyChecker  跨年一致性比对                             │
│ - ConfidenceScorer       置信度评分 + 异常标记                     │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│ 输出层                                                              │
│ - JSONExporter          结构化JSON (含元数据)                       │
│ - DatabaseWriter        SQLite/PostgreSQL                          │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块设计

### 3.1 CIDFontDetector (重构)

**现状问题**: 仅扫描前20页，大型年报(300+页)CF页在50页之后导致漏检

**改进方案**:

```python
class CIDFontDetector:
    def scan_all_pages(self, pdf_path) -> Dict[int, float]:
        """全页扫描，返回每页CID概率"""
        results = {}
        for page_num in range(total_pages):
            # 策略1: 数值密度扫描（财务报表页通常高数值密度）
            # 策略2: 字符替换率扫描
            # 策略3: 字体名检测（识别CID前缀）
            results[page_num] = self._calculate_cid_probability(page)
        return results
```

**触发阈值**: 从30%降至15%

### 3.2 MultiEngineExtractor

**引擎选择逻辑**:

```
PDF输入
    │
    ▼
┌───────────────────┐
│ 尝试 pdfplumber   │──→ 正常文本? ──→ 输出
└───────────────────┘
    │
    ▼ (检测到CID)
┌───────────────────┐
│ 尝试 PyMuPDF      │──→ 可解码? ──→ 一致性验证 ──→ 输出
└───────────────────┘
    │
    ▼ (PyMuPDF失败)
┌───────────────────┐
│ 尝试 pdf2htmlEX   │──→ HTML结构提取 ──→ 交叉验证
└───────────────────┘
    │
    ▼ (极端CID)
┌───────────────────┐
│ 尝试 TesseractOCR │──→ 位置+文本输出
└───────────────────┘
```

**交叉验证**: 两引擎结果一致性 > 95% → 高置信度

### 3.3 SemanticRecovery (核心创新)

**三层恢复策略**:

1. **pdf2htmlEX文本提取**: HTML保留文本结构，提取带位置的文本
2. **词汇推断**: 基于位置+上下文的科目名推断（500+财务科目词库）
3. **OCR兜底**: 极端CID字体使用Tesseract

**科目名恢复流程**:
```
CID乱码文本 → pdf2htmlEX位置信息 → 词汇表匹配 → 上下文推断 → 标准科目名
```

**词库覆盖**: 500+ 常见财务科目（资产负债表、利润表、现金流量表各科目）

### 3.4 ChartOfAccountsMapper (CAS标准)

**三级映射架构**:

```
公司原始科目 ──→ CAS中间标准 ──→ 目标口径
     │              │
     ▼              ▼
  原始名称      CAS_2024_标准
  (保留)        科目代码+名称
```

**行业适配**:
- 通用: 标准CAS科目映射
- 银行: 金融机构专项映射
- 保险: 保费/赔付/准备金专项映射

### 3.5 QualityGate (零容忍验证)

**勾稽关系校验**:

| 校验规则 | 公式 |
|----------|------|
| 资产负债表平衡 | 资产总计 = 负债合计 + 所有者权益合计 |
| 利润表结转 | 期初未分配利润 + 本期净利润 = 期末未分配利润 |
| 现金流量平衡 | 现金净增加额 = 期末现金 - 期初现金 |

**异常标记**:
```python
{
    "quality_flags": ["BALANCE_CHECK_FAILED", "OUTLIER_DETECTED"],
    "confidence": 0.85,
    "verification_results": {...}
}
```

---

## 4. 数据模型

### 4.1 输出JSON结构

```json
{
  "statement_type": "balance_sheet",
  "stock_code": "601628",
  "stock_name": "中国人寿",
  "fiscal_year": 2024,
  "extracted_at": "2026-05-11T10:00:00",
  "found": true,
  "confidence": 0.98,
  "quality_flags": [],
  "data": {
    "货币资金": {"value": 123456789012, "unit": "元", "source_pages": [7, 8]},
    "应收账款": {"value": 23456789012, "unit": "元", "source_pages": [9]}
  },
  "metadata": {
    "extraction_method": "pdfplumber+html_recovery",
    "cid_pages_detected": [22, 23, 24],
    "recovery_applied": true
  }
}
```

### 4.2 数据库Schema

```sql
CREATE TABLE financial_data (
    id INTEGER PRIMARY KEY,
    stock_code TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    statement_type TEXT NOT NULL,
    item_name_original TEXT NOT NULL,
    item_name_cas TEXT,
    item_code_cas TEXT,
    value REAL NOT NULL,
    unit TEXT DEFAULT '元',
    confidence REAL,
    quality_flags TEXT,
    source_pages TEXT,
    extraction_method TEXT,
    extracted_at TIMESTAMP,
    UNIQUE(stock_code, fiscal_year, statement_type, item_name_original)
);
```

---

## 5. 实施路线图

| 阶段 | 内容 | 交付物 | 优先级 |
|------|------|--------|--------|
| **Phase 1** | CID检测窗口修复 + 阈值调整 | `CIDFontDetector` 重构，全页扫描 | P0 |
| **Phase 2** | SemanticRecovery语义重建 | 科目名恢复流程，500+词库 | P0 |
| **Phase 3** | CAS科目映射体系 | `ChartOfAccountsMapper` 实现 | P1 |
| **Phase 4** | 质量门控 + 交叉验证 | `QualityGate` 实现，勾稽校验 | P1 |
| **Phase 5** | 多引擎Validator | `EngineValidator` 多引擎交叉验证 | P2 |
| **Phase 6** | 全量测试 + 边界Case | 39只股票全量回归测试 | P2 |

### Phase 1 详细任务
1. 重构 `CIDFontDetector.scan_all_pages()` 替代现有20页限制
2. 降低 `is_garbled_text()` 阈值从30%到15%
3. 添加数值密度扫描作为补充检测手段
4. 验证601628/600016等已知问题文件

### Phase 2 详细任务
1. 实现 `SemanticRecovery.recover_item_names()` 
2. 构建500+财务科目词库（BS/IS/CF各科目）
3. 集成pdf2htmlEX文本提取到recovery流程
4. 实现词汇推断算法（位置+上下文）

---

## 6. 已知失败案例修复

| 文件 | 当前问题 | 修复方案 |
|------|----------|----------|
| 601628 三大表 | Recovery丢失科目名 | Phase 2 SemanticRecovery |
| 600016 CF | 仅扫描前20页漏检 | Phase 1 全页扫描 |
| 600030 IS | 619项列对齐错误 | Phase 5 交叉验证 |
| 601668 IS | tolerance=20不适应宽表 | 自适应容差算法 |

---

## 7. 验收标准

### 7.1 功能验收
- [ ] 39只股票200个JSON文件100%成功提取
- [ ] 数值与PDF原文误差为零
- [ ] 科目名称成功映射到CAS标准
- [ ] 单位统一转换为"元"

### 7.2 质量验收
- [ ] 三大表勾稽关系100%通过
- [ ] 置信度评分与实际质量一致
- [ ] 异常情况正确标记

### 7.3 性能验收
- [ ] 单PDF三大表提取 < 2分钟
- [ ] 批量处理39只股票 < 1小时

---

## 8. 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| OCR精度不足 | 低 | 高 | 词汇推断 + 交叉验证双重保障 |
| 新PDF格式未知 | 中 | 中 | 持续扩充词库 + 人工标记通道 |
| CAS映射覆盖不足 | 中 | 中 | 保留原始名称作为兜底 |
| 性能不达标 | 低 | 中 | 多进程并行 + Parser实例复用 |

---

## 9. 后续优化方向

1. **支持IFRS**: 在CAS基础上增加IFRS双口径映射
2. **实时年报**: 支持半年度/季度报告
3. **可视化校验**: Web界面展示提取结果供人工复核
4. **增量更新**: 支持年报增量更新而非全量重提
