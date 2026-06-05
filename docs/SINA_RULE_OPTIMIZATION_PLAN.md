# Sina 数据渠道规则优化 — 阶段性工作计划

**创建日期**: 2026-06-04
**最后更新**: 2026-06-04
**状态**: 进行中
**目标**: 通过分阶段扩大 Sina vs RDS 对比范围，将匹配规则优化到更完整更好的程度

---

## 📋 总目标

| 维度 | 当前 (2026-06-04) | 最终目标 |
|------|-------------------|----------|
| **BS 匹配率** | 99.59% (120 stocks) | ≥ 99.85% |
| **IS 匹配率** | 98.90% (120 stocks) | ≥ 99.50% |
| **CF 匹配率** | 87.54% (120 stocks) | ≥ 92% |
| **对比覆盖** | 0.93% (1784 / 192,739) | ≥ 30% (60,000+ 比较) |
| **规则数** | 56 aliases + 2 aggs | ≥ 200 aliases + 20 aggs |
| **测试覆盖** | 30 tests | ≥ 50 tests |

---

## 🛠 阶段计划

### 阶段 1: 扩展时间窗口 (2000-2022 全期 23 年)

**目标**: 把 baseline 从 2019-2022 (3 年) 扩展到 2000-2022 (23 年), 209 stocks 不变

**预期产出**:
- 1,784 → ~10,000 比较 (提升 ~6×)
- CF 85.64% → ~88% (找到更多历史时段的别名)
- 暴露 2000-2010 早期 Sina 格式特殊项

**执行步骤**:
1. [ ] 1.1 修改 `scripts/baseline_2019_2022.py` 支持 `--years 2000..2022` 大范围
2. [ ] 1.2 跑 baseline (约 30-60 分钟)
3. [ ] 1.3 分析按年份的匹配率变化 (找历史断点)
4. [ ] 1.4 提取 2000-2010 期间的未匹配项 → 写入 `rules/aliases_legacy.yaml`
5. [ ] 1.5 重跑 baseline 验证提升
6. [ ] 1.6 提交 + 更新 `data/ground_truth_reports/cleaning_progression.md`

**当前进度**: ⏳ 未开始

---

### 阶段 2: 全期学习新别名 (23 年滚动学习)

**目标**: 用 23 年数据让 `learn_sina_aliases.py` 发现更多历史时段的别名

**预期产出**:
- 50 → ~150 aliases (累计 200+ 总规则)
- BS 99.59% → ~99.75%
- 暴露行业特化早期格式 (2002-2008 银行、保险)

**执行步骤**:
1. [ ] 2.1 用 2000-2022 全期跑 `learn_sina_aliases.py`
2. [ ] 2.2 人工审核新规则 (去掉虚假匹配, 命名规范)
3. [ ] 2.3 增量合并到 `rules/aliases.yaml` (sina_aliases_2019_2022 段)
4. [ ] 2.4 同样跑全期 `learn_sina_aliases.py` 找 aggregations
5. [ ] 2.5 重跑 baseline 验证
6. [ ] 2.6 提交 + 更新规则文件 + 写新规则到 cleaning_progression

**当前进度**: ⏳ 未开始

---

### 阶段 3: 扩展股票到 1000+ (按行业分层)

**目标**: 把 baseline 股票从 209 扩到 1000+ (按 prefix 6 组 × ~200 抽样)

**预期产出**:
- 1,784 → ~30,000+ 比较
- CF 88% → ~92% (更多行业/边缘案例覆盖)
- 发现新兴行业 (新能源, 半导体) 特有科目

**执行步骤**:
1. [ ] 3.1 生成 1000+ 股票列表 (按 prefix × 行业分层抽样)
2. [ ] 3.2 跑 baseline 2000-2022 (约 3-6 小时)
3. [ ] 3.3 分析 per-prefix 匹配率, 识别需行业特化规则的子组
4. [ ] 3.4 写行业特化规则 (银行/保险/证券/房地产/新能源/科技)
5. [ ] 3.5 重跑 baseline
6. [ ] 3.6 提交 + 最终报告

**当前进度**: ⏳ 未开始

---

## 📊 进度跟踪区 (每次做完更新这里)

### 阶段 1 进度
- 开始时间: _TBD_
- 1.1 baseline 支持 2000-2022: _未开始_
- 1.2 跑 baseline: _未开始_
- 1.3 按年份分析: _未开始_
- 1.4 提取 2000-2010 别名: _未开始_
- 1.5 重跑验证: _未开始_
- 1.6 提交 + 报告: _未开始_
- **阶段 1 完成时间**: _TBD_
- **阶段 1 末匹配率**: _TBD_

### 阶段 2 进度
- 开始时间: _TBD_
- 2.1 全期 learn_sina_aliases: _未开始_
- 2.2 人工审核: _未开始_
- 2.3 合并到 aliases.yaml: _未开始_
- 2.4 全期找 aggregations: _未开始_
- 2.5 重跑 baseline: _未开始_
- 2.6 提交 + 报告: _未开始_
- **阶段 2 完成时间**: _TBD_
- **阶段 2 末匹配率**: _TBD_
- **累计 aliases 数**: _TBD_

### 阶段 3 进度
- 开始时间: _TBD_
- 3.1 1000+ 股票列表: _未开始_
- 3.2 跑 1000+ baseline: _未开始_
- 3.3 按 prefix 分析: _未开始_
- 3.4 行业特化规则: _未开始_
- 3.5 重跑 baseline: _未开始_
- 3.6 提交 + 报告: _未开始_
- **阶段 3 完成时间**: _TBD_
- **阶段 3 末匹配率**: _TBD_

---

## 📝 关键文件 (供下个 session 参考)

| 文件 | 用途 |
|------|------|
| `scripts/baseline_2019_2022.py` | baseline 测量 (可重命名/扩展) |
| `scripts/learn_sina_aliases.py` | 别名学习 |
| `rules/aliases.yaml` | 规则主文件 (sina_aliases_2019_2022 段) |
| `rules/cf_direct_items.yaml` | CF 直接法白名单 |
| `rules/industry_aliases.yaml` | 行业股票映射 |
| `data/ground_truth_reports/expanded_stock_list.txt` | 当前 209 股票列表 |
| `data/ground_truth_reports/baseline_2019_2022.json` | 最新 baseline 结果 |
| `data/ground_truth_reports/cleaning_progression.md` | 历史进展报告 |
| `docs/SINA_RULE_OPTIMIZATION_PLAN.md` | **本文档 (主计划)** |

---

## 🔄 恢复指引 (被打断后如何继续)

1. **读本文档的"进度跟踪区"** — 知道当前到哪
2. **找到第一个未完成 [ ]** — 就是下一步
3. **运行相关脚本**:
   - baseline: `python scripts/baseline_2019_2022.py --years <range> --source sina`
   - learn: `python scripts/learn_sina_aliases.py --stocks <list> --years <range>`
4. **更新进度跟踪区** (修改 _未开始_ → _进行中_ → _完成_)
5. **提交**: `git add -A && git commit -m "phase X: <description>"`

---

## ⚠ 注意事项

- RDS 数据路径: `D:/Research/Quant/SETL/cninfo/data_backup` (Windows, pyreadr 较慢)
- 23 年 × 3,000+ stocks × 3 stmts 可能耗时 1-2 天
- 中间打断时, **务必更新进度区** 以便下次能继续
- 每次扩展都要保留旧的 209-stocks 结果作 baseline (防止回归)

---

**下次开始时, 先读 "进度跟踪区" 找第一个 [ ], 然后按恢复指引继续。**
