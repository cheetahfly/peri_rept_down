# -*- coding: utf-8 -*-
"""
完整测试 akshare 各渠道的 600519 2020 年报现金流量表数据。

测试渠道清单：
  1. EM 按年度       stock_cash_flow_sheet_by_yearly_em
  2. EM 按季度       stock_cash_flow_sheet_by_quarterly_em
  3. EM 按报告期     stock_cash_flow_sheet_by_report_em
  4. EM 退市股       stock_cash_flow_sheet_by_report_delisted_em（应不返回结果）
  5. THS 旧版 按报告期  stock_financial_cash_ths(indicator='按报告期')
  6. THS 旧版 按年度    stock_financial_cash_ths(indicator='按年度')
  7. THS 旧版 按单季度  stock_financial_cash_ths(indicator='按单季度')
  8. THS 新版 按报告期  stock_financial_cash_new_ths(indicator='按报告期')
  9. THS 新版 按年度    stock_financial_cash_new_ths(indicator='按年度')
  10. Sina 现金流量表  stock_financial_report_sina(symbol='现金流量表')

所有原始返回数据保存到 tmp/akshare_test_600519_2020/
"""
import os
import sys
import json
import traceback
import warnings

warnings.filterwarnings("ignore")
import akshare as ak  # noqa: E402

OUT_DIR = "tmp/akshare_test_600519_2020"
os.makedirs(OUT_DIR, exist_ok=True)

STOCK_NUMERIC = "600519"
STOCK_EM = "SH600519"
STOCK_SINA = "sh600519"


def save_result(label: str, df, error: str = None, extra: dict = None) -> dict:
    """保存原始返回到 CSV + JSON，返回 metadata。"""
    meta = {
        "channel": label,
        "error": error,
        "row_count": 0,
        "col_count": 0,
        "columns": [],
        "csv": None,
        "extra": extra or {},
    }
    if error:
        meta_path = os.path.join(OUT_DIR, f"meta_{label}.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return meta

    if df is None or len(df) == 0:
        meta["error"] = "empty_result"
        meta_path = os.path.join(OUT_DIR, f"meta_{label}.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return meta

    csv_path = os.path.join(OUT_DIR, f"raw_{label}.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    meta.update({
        "row_count": int(len(df)),
        "col_count": int(len(df.columns)),
        "columns": [str(c) for c in df.columns],
        "csv": csv_path,
        "head_first_row": {str(k): (str(v) if v is not None else None) for k, v in df.iloc[0].to_dict().items()},
    })
    meta_path = os.path.join(OUT_DIR, f"meta_{label}.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


def try_call(label: str, fn, **kwargs) -> dict:
    print(f"\n[{label}] call {fn.__name__}({kwargs})")
    try:
        df = fn(**kwargs)
        meta = save_result(label, df, extra={"call_args": {k: str(v) for k, v in kwargs.items()}})
        print(f"  [OK] rows={meta['row_count']} cols={meta['col_count']}")
        if meta["columns"]:
            print(f"  cols(first10): {meta['columns'][:10]}")
        return meta
    except Exception as e:
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        meta = save_result(label, None, error=err, extra={"call_args": {k: str(v) for k, v in kwargs.items()}})
        print(f"  [FAIL] {type(e).__name__}: {e}")
        return meta


def main():
    summary = []

    # ---- EM 四个接口 ----
    summary.append(try_call(
        "01_em_yearly",
        ak.stock_cash_flow_sheet_by_yearly_em,
        symbol=STOCK_EM,
    ))
    summary.append(try_call(
        "02_em_quarterly",
        ak.stock_cash_flow_sheet_by_quarterly_em,
        symbol=STOCK_EM,
    ))
    summary.append(try_call(
        "03_em_report",
        ak.stock_cash_flow_sheet_by_report_em,
        symbol=STOCK_EM,
    ))
    summary.append(try_call(
        "04_em_report_delisted",
        ak.stock_cash_flow_sheet_by_report_delisted_em,
        symbol=STOCK_EM,
    ))

    # ---- THS 旧版 三个 indicator ----
    for ind_label, ind_value in [
        ("05_ths_old_report",  "按报告期"),
        ("06_ths_old_yearly",  "按年度"),
        ("07_ths_old_single_q","按单季度"),
    ]:
        summary.append(try_call(
            ind_label,
            ak.stock_financial_cash_ths,
            symbol=STOCK_NUMERIC,
            indicator=ind_value,
        ))

    # ---- THS 新版 两个 indicator ----
    for ind_label, ind_value in [
        ("08_ths_new_report",  "按报告期"),
        ("09_ths_new_yearly",  "按年度"),
    ]:
        summary.append(try_call(
            ind_label,
            ak.stock_financial_cash_new_ths,
            symbol=STOCK_NUMERIC,
            indicator=ind_value,
        ))

    # ---- Sina 综合接口 ----
    summary.append(try_call(
        "10_sina_cf",
        ak.stock_financial_report_sina,
        stock=STOCK_SINA,
        symbol="现金流量表",
    ))

    # 汇总
    summary_path = os.path.join(OUT_DIR, "_download_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "="*70)
    print("Download Summary:")
    print(f"{'channel':30s} {'status':10s} {'rows':>6s} {'cols':>6s}")
    print("-" * 70)
    for m in summary:
        if m["error"]:
            status = "ERROR" if m["error"] != "empty_result" else "EMPTY"
        else:
            status = "OK"
        print(f"{m['channel']:30s} {status:10s} {m['row_count']:>6d} {m['col_count']:>6d}")
    print(f"\nSummary file: {summary_path}")


if __name__ == "__main__":
    main()
