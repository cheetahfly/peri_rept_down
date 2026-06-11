# -*- coding: utf-8 -*-
"""
多股多渠道现金流量表下载测试。

测试范围（按用户要求）：
  - 5 个渠道：EM yearly / EM report / EM delisted / THS new report / THS new yearly
  - 5 只股票：600519/600036/000651/688981/300750（4 个板块）
  - 数据：2020 年报现金流量表（含直接法+间接法）

每次调用保存到 tmp/akshare_test_multi_stocks_2020/raw_{stock}_{channel}.csv
"""
import os
import json
import time
import traceback
import warnings

warnings.filterwarnings("ignore")
import akshare as ak  # noqa: E402

OUT_DIR = "tmp/akshare_test_multi_stocks_2020"
os.makedirs(OUT_DIR, exist_ok=True)

# (code, name, board, em_symbol)
STOCKS = [
    ("600887", "伊利股份", "上海主板",    "SH600887"),
    ("600036", "招商银行", "上海主板(金融)", "SH600036"),
    ("000651", "格力电器", "深圳主板",    "SZ000651"),
    ("688981", "中芯国际", "上海科创板",   "SH688981"),
    ("300750", "宁德时代", "深圳创业板",   "SZ300750"),
]

# (label, fn, kwargs_template)
CHANNELS = [
    ("em_yearly",        ak.stock_cash_flow_sheet_by_yearly_em,            {"symbol_key": "em_symbol"}),
    ("em_report",        ak.stock_cash_flow_sheet_by_report_em,            {"symbol_key": "em_symbol"}),
    ("em_delisted",      ak.stock_cash_flow_sheet_by_report_delisted_em,   {"symbol_key": "em_symbol"}),
    ("ths_new_report",   ak.stock_financial_cash_new_ths,                  {"symbol_key": "code",      "extra": {"indicator": "按报告期"}}),
    ("ths_new_yearly",   ak.stock_financial_cash_new_ths,                  {"symbol_key": "code",      "extra": {"indicator": "按年度"}}),
]


def call(fn, stock, channel_cfg):
    key = channel_cfg["symbol_key"]
    if key == "em_symbol":
        symbol = stock[3]
    elif key == "code":
        symbol = stock[0]
    else:
        raise ValueError(key)
    kwargs = {"symbol": symbol}
    kwargs.update(channel_cfg.get("extra", {}))
    return fn(**kwargs)


def main():
    summary = []
    for stock in STOCKS:
        code, name, board, em_sym = stock
        for ch_label, fn, cfg in CHANNELS:
            tag = f"{code}_{ch_label}"
            print(f"\n[{tag}] {name} ({board}) - {fn.__name__}")
            try:
                t0 = time.time()
                df = fn(**({"symbol": (em_sym if cfg["symbol_key"]=="em_symbol" else code)} | cfg.get("extra", {})))
                dt = time.time() - t0
                meta = {
                    "stock_code": code, "stock_name": name, "board": board,
                    "channel": ch_label, "rows": int(len(df)), "cols": int(len(df.columns)),
                    "elapsed_sec": round(dt, 2), "error": None,
                }
                if len(df) > 0:
                    csv_path = os.path.join(OUT_DIR, f"raw_{tag}.csv")
                    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                    meta["csv"] = csv_path
                else:
                    meta["error"] = "empty"
                print(f"  [OK] rows={meta['rows']} cols={meta['cols']} t={dt:.1f}s")
            except Exception as e:
                meta = {
                    "stock_code": code, "stock_name": name, "board": board,
                    "channel": ch_label, "rows": 0, "cols": 0,
                    "error": f"{type(e).__name__}: {e}",
                    "traceback": traceback.format_exc(),
                }
                print(f"  [FAIL] {type(e).__name__}: {e}")
            summary.append(meta)
            time.sleep(0.5)  # 礼貌延迟

    summary_path = os.path.join(OUT_DIR, "_download_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 控制台汇总
    print("\n" + "="*80)
    print("Download Summary")
    print(f"{'stock':10s} {'channel':18s} {'rows':>6s} {'cols':>6s} {'status':>10s}")
    print("-"*80)
    for m in summary:
        status = "OK" if not m["error"] else ("EMPTY" if m["error"]=="empty" else "ERROR")
        print(f"{m['stock_code']:10s} {m['channel']:18s} {m['rows']:>6d} {m['cols']:>6d} {status:>10s}")
    print(f"\nSummary: {summary_path}")


if __name__ == "__main__":
    main()
