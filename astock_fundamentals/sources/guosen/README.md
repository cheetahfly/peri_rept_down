# 国信证券数据源 (GuosenLoader)

对接国信证券财务数据 skill。提供与 SinaLoader 兼容的接口 (`read_statement`, `get_annual`)。

## API Key 配置

按以下优先级加载：

1. 构造参数 `GuosenLoader(api_key="...")`
2. 环境变量 `GS_API_KEY`
3. 项目根 `./memory.md` 中 `GS_API_KEY=...` 字段

### Windows PowerShell
```powershell
$env:GS_API_KEY="your_key"
```

### Linux/macOS
```bash
export GS_API_KEY="your_key"
```

## 用法

```python
from astock_fundamentals.sources.guosen import GuosenLoader

loader = GuosenLoader()  # 从环境变量读取 API key
df = loader.get_annual(
    stock_code="600519",
    target_years=[2019, 2020, 2021, 2022],
    statement_type="balance_sheet",  # 或 income_statement / cash_flow
)
print(df.head())
```

CLI:

```bash
python scripts/clean_sina_pipeline.py --source guosen --stocks 600519 --years 2019 2020
python scripts/baseline_2019_2022.py --source guosen
```

## 港股支持

```python
df = loader.read_statement("02020", "balance_sheet")  # 港股 (自动 market=HK)
```

## 限制

- 网络依赖：必须能访问 `https://dgzt.guosen.com.cn`
- 调用频率限制：依赖国信 API 配额
- 字段名预期与 Sina 中文名一致 (待 Task 7 验证)