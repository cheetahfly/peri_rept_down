# 间接法现金流量表数据下载设计

**创建日期**: 2026-06-08
**项目**: peri_rept_down (A股财务数据多源清洗流水线)
**范围**: 下载所有 A 股上市公司的间接法 CF 数据
**数据源**: Sina (AKShare) 同花顺接口 `stock_financial_cash_ths`

## 1. 目标

通过 Sina 渠道下载所有 A 股上市公司（约 3,902 只股票）在 RDS 标准数据库中 2020-2022 年报的间接法计算的现金流量表数据，按照项目固有的 Tidy CSV 规则存放在本地。

## 2. 关键决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 下载范围 | 全部 3,902 只股票 | 覆盖最完整 |
| 年份范围 | 仅 2020-2022 年报 | RDS 标准数据库有的时间切面 |
| 存储格式 | Tidy CSV (与现有 `sina_cleaned_*.csv` 一致) | 可直接被后续处理复用 |
| 网络异常处理 | 重试 3 次后跳过 | 耗时可控，稳健 |
| 下载方案 | 串行 + 断点续传 | 避免触发限流，可暂停 |

## 3. 架构

```
scripts/download_indirect_cf.py
    │
    ├── 读取 full_stock_list.txt (3,902 只股票)
    ├── 读取 progress.json (断点续传)
    ├── 筛选 RDS 有 2020-2022 年报数据的股票
    │
    └── 对每只股票:
        ├── 调用 akshare.stock_financial_cash_ths(symbol)
        ├── 解析间接法调节项 (列索引 47-64)
        ├── 筛选 2020-2022 年报 (报告日期 12-31)
        ├── 转换为 Tidy 格式
        ├── 保存到 data/exports_v2/indirect_cf/{stock_code}.csv
        └── 更新 progress.json
```

## 4. 数据格式

### 4.1 Tidy CSV 规范

```csv
stock_code,year,period,statement_type,field_code,field_name,value,display_order
000001,2020,annual,cash_flow,F057N,净利润,42633000000.0,1
000001,2020,annual,cash_flow,F058N,加：资产减值准备,160000000.0,2
000001,2020,annual,cash_flow,F059N,固定资产折旧,3268000000.0,3
000001,2020,annual,cash_flow,F060N,无形资产摊销,849000000.0,4
...
```

### 4.2 字段映射 (列索引 → F-code)

| 索引 | 间接法字段 | F-code | display_order |
|------|------------|--------|---------------|
| 47 | 净利润 | F057N | 1 |
| 48 | 资产减值准备 | F058N | 2 |
| 49 | 固定资产折旧 | F059N | 3 |
| 50 | 无形资产摊销 | F060N | 4 |
| 51 | 长期待摊费用摊销 | F061N | 5 |
| 52 | 处置固定资产损失 | F062N | 6 |
| 53 | 固定资产报废损失 | F063N | 7 |
| 54 | 公允价值变动损失 | F064N | 8 |
| 56 | 投资损失 | F065N | 9 |
| 57 | 递延所得税资产减少 | F066N | 10 |
| 58 | 递延所得税负债增加 | F067N | 11 |
| 59 | 存货的减少 | F068N | 12 |
| 60 | 经营性应收项目的减少 | F069N | 13 |
| 61 | 经营性应付项目的增加 | F070N | 14 |
| 62 | 其他 | F071N | 15 |

## 5. 存储路径

- **数据目录**: `data/exports_v2/indirect_cf/`
- **文件命名**: `{stock_code}.csv` (例如 `000001.csv`)
- **进度文件**: `data/ground_truth_reports/indirect_cf_progress.json`
- **日志文件**: `data/ground_truth_reports/indirect_cf_download.log`

## 6. 错误处理

- **网络超时**: 重试 3 次，指数退避 (1s, 2s, 4s)
- **数据缺失**: 标记为 `no_data`，跳过
- **解析错误**: 记录到日志，继续处理下一只
- **中断恢复**: 进度文件实时保存，可中断后继续

## 7. 验证检查点

| 步骤 | 验证命令 | 预期结果 |
|------|----------|----------|
| 下载完成 | `wc -l data/exports_v2/indirect_cf/*.csv` | 每只股票约 15-45 行 |
| 数据格式 | `head -3 data/exports_v2/indirect_cf/000001.csv` | 显示 3 行 Tidy 格式 |
| 进度检查 | `cat data/ground_truth_reports/indirect_cf_progress.json \| head -20` | 显示完成进度 |
| 与 RDS 对比 | 运行对比脚本 | 准确率应高于直接法对比 |

## 8. 约束

- **不修改业务代码**: 仅新增下载脚本和输出目录
- **不重跑**: 已下载的不重新下载（断点续传）
- **限流控制**: 串行下载，每次请求间隔 0.5s
