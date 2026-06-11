# -*- coding: utf-8 -*-
"""
对比各 akshare 渠道与 RDS 标准数据。

策略：value-based matching
  - RDS 49个item为基准（每个有item_code/item_name/value）
  - 对每个渠道，提取2020年报记录的所有数值
  - 对每个RDS item，在channel的values中找匹配
  - 匹配规则：|v_channel - v_rds| < 0.01元（精确到分）
  - 若channel值精度只到万/亿，则计算相对误差

输出：
  - tmp/akshare_test_600519_2020/_quality_report.json
  - tmp/akshare_test_600519_2020/_quality_report.md
"""
import os
import sys
import json
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

OUT_DIR = "tmp/akshare_test_600519_2020"
RDS_FILE = os.path.join(OUT_DIR, "rds_standard_600519_2020_cf.json")


def load_rds():
    with open(RDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_value(v):
    """转 float 或返回 None。支持 '亿'/'万' 单位字符串。"""
    if v is None or v == "" or pd.isna(v):
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s or s.lower() in ("false", "true", "nan"):
            return None
        # 处理 '1070.24亿' / '516.69万'
        multiplier = 1.0
        if s.endswith("亿"):
            multiplier = 1e8
            s = s[:-1]
        elif s.endswith("万亿"):
            multiplier = 1e12
            s = s[:-2]
        elif s.endswith("万"):
            multiplier = 1e4
            s = s[:-1]
        elif s.endswith("%"):
            return None  # 百分比不参与对比
        try:
            return float(s) * multiplier
        except (ValueError, TypeError):
            return None
    try:
        f = float(v)
        if f == 0.0:
            return None
        return f
    except (ValueError, TypeError):
        return None


def extract_em_2020_values(csv_path):
    """EM 系列：行=报告期，列=英文字段名。返回 {col_name_en: value}"""
    df = pd.read_csv(csv_path)
    df["REPORT_DATE"] = df["REPORT_DATE"].astype(str)
    mask = df["REPORT_DATE"].str.startswith("2020-12-31")
    if mask.sum() == 0:
        return {}
    r = df[mask].iloc[0].to_dict()
    exclude = {"SECUCODE","SECURITY_CODE","SECURITY_NAME_ABBR","ORG_CODE","ORG_TYPE",
               "REPORT_DATE","REPORT_TYPE","REPORT_DATE_NAME","SECURITY_TYPE_CODE",
               "NOTICE_DATE","UPDATE_DATE","CURRENCY","LISTING_STATE","OPINION_TYPE",
               "OPDATE","OSOPINION_TYPE"}
    out = {}
    for c, v in r.items():
        if c in exclude or c.endswith("_YOY"):
            continue
        nv = normalize_value(v)
        if nv is not None:
            out[c] = nv
    return out


def extract_ths_old_2020_values(csv_path):
    """THS old：行=报告期，列=中文字段名。
    报告期可能为 '2020-12-31' 或 INT 2020 （indicator=按年度时）。
    """
    df = pd.read_csv(csv_path)
    date_col = "报告期"
    s = df[date_col].astype(str)
    mask = s.str.startswith("2020-12-31") | (s == "2020") | (s == "2020.0")
    if mask.sum() == 0:
        return {}
    r = df[mask].iloc[0].to_dict()
    out = {}
    for c, v in r.items():
        if c == date_col:
            continue
        nv = normalize_value(v)
        if nv is not None:
            out[c] = nv
    return out


def extract_sina_2020_values(csv_path):
    """Sina：报告日为 INT YYYYMMDD 格式。"""
    df = pd.read_csv(csv_path)
    s = df["报告日"].astype(str)
    mask = s.str.startswith("20201231") | s.str.startswith("2020-12-31")
    if mask.sum() == 0:
        return {}
    r = df[mask].iloc[0].to_dict()
    out = {}
    for c, v in r.items():
        if c == "报告日":
            continue
        nv = normalize_value(v)
        if nv is not None:
            out[c] = nv
    return out


def extract_ths_new_2020_values(csv_path):
    """THS new：长格式 metric_name + value。"""
    df = pd.read_csv(csv_path)
    df["report_date"] = df["report_date"].astype(str)
    mask = df["report_date"].str.startswith("2020-12-31")
    sub = df[mask]
    if len(sub) == 0:
        return {}
    out = {}
    for _, row in sub.iterrows():
        name = row.get("metric_name")
        v = row.get("value")
        nv = normalize_value(v)
        if name and nv is not None:
            out[str(name)] = nv
    return out


def extract_sina_2020_values_OLD(csv_path):
    """旧版sina extractor，已被上方替换。"""
    return {}


def best_match(rds_value, channel_values):
    """在 channel_values 中找到最接近 rds_value 的值。
    返回 (matched_label, matched_value, abs_diff, rel_err_pct)
    若 abs_diff < 0.01 视为精确匹配（精确到分）
    """
    best = None
    best_diff = None
    for label, v in channel_values.items():
        diff = abs(v - rds_value)
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best = (label, v)
    if best is None:
        return None, None, None, None
    rel_err = (best_diff / abs(rds_value) * 100) if rds_value != 0 else 0.0
    return best[0], best[1], best_diff, rel_err


def compare_channel(channel_name, channel_values, rds_items, exact_tol=0.01):
    """对一个渠道做完整对比。

    分类：
      - exact: |diff| < 0.01元
      - precision_loss: 0.01 <= |diff| < 1元（精度损失）
      - rounded:  rel_err < 1% （万元/亿元精度）
      - large_err: rel_err >= 1% （严重不一致）
      - no_match: 完全找不到
    """
    results = []
    n_exact = n_prec = n_round = n_large = n_no = 0

    for item in rds_items:
        rds_v = item["value"]
        if rds_v is None or rds_v == 0:
            continue
        label, ch_v, diff, rel_err = best_match(rds_v, channel_values)
        if label is None:
            n_no += 1
            cls = "no_data_in_channel"
        elif diff < exact_tol:
            n_exact += 1
            cls = "exact"
        elif diff < 1.0:
            n_prec += 1
            cls = "precision_sub_yuan"
        elif rel_err < 1.0:
            n_round += 1
            cls = "rounded_or_aggregated"
        else:
            n_large += 1
            cls = "large_error"
        results.append({
            "rds_item_code": item["item_code"],
            "rds_item_name": item["item_name"],
            "rds_value": rds_v,
            "ch_label": label,
            "ch_value": ch_v,
            "abs_diff": diff,
            "rel_err_pct": rel_err,
            "class": cls,
        })

    total_real = len(results)
    summary = {
        "channel": channel_name,
        "channel_value_count": len(channel_values),
        "rds_items_compared": total_real,
        "exact_match": n_exact,
        "precision_sub_yuan": n_prec,
        "rounded_or_aggregated": n_round,
        "large_error": n_large,
        "no_match": n_no,
        "exact_match_rate": (n_exact / total_real * 100) if total_real else 0,
    }
    return summary, results


def detect_indirect_method(channel_values):
    """检查渠道是否包含间接法CF的关键字段。

    间接法关键标志（出现≥3个即认为支持间接法）。
    """
    keywords_zh = [
        "净利润", "资产减值", "信用减值", "固定资产折旧", "无形资产摊销",
        "长期待摊", "公允价值", "投资损失", "递延", "存货", "经营性应收",
        "经营性应付", "现金的期末", "现金的期初", "财务费用",
    ]
    keywords_en = [
        # EM 英文
        "NETPROFIT", "FA_IR_DEPR", "OILGAS_BIOLOGY_DEPR", "IA_AMORTIZE",
        "LPE_AMORTIZE", "FAIRVALUE_CHANGE_LOSS", "INVEST_LOSS", "DEFER_TAX",
        "DT_ASSET_REDUCE", "DT_LIAB_ADD", "INVENTORY_REDUCE",
        "OPERATE_RECE_REDUCE", "OPERATE_PAYABLE_ADD", "NETCASH_OPERATENOTE",
        "END_CASH", "BEGIN_CASH", "CCE_ADDNOTE",
        # THS new 英文
        "net_profit", "cash_net_profit", "assets_impairment", "depreciation",
        "amortization", "investment_loss", "deferred", "inventory_decrease",
        "inventory_addition", "operating_receivable", "operating_payable",
        "fair_value", "credit_impairment",
    ]
    found = []
    for label in channel_values:
        s = str(label)
        s_upper = s.upper()
        s_lower = s.lower()
        for kw in keywords_zh:
            if kw in s:
                found.append(label)
                break
        else:
            for kw in keywords_en:
                if kw in s_upper or kw in s_lower:
                    found.append(label)
                    break
    return len(found), found[:20]


CHANNELS = [
    ("01_em_yearly",          "raw_01_em_yearly.csv",          extract_em_2020_values),
    ("02_em_quarterly",       "raw_02_em_quarterly.csv",       extract_em_2020_values),
    ("03_em_report",          "raw_03_em_report.csv",          extract_em_2020_values),
    ("04_em_report_delisted", "raw_04_em_report_delisted.csv", extract_em_2020_values),
    ("05_ths_old_report",     "raw_05_ths_old_report.csv",     extract_ths_old_2020_values),
    ("06_ths_old_yearly",     "raw_06_ths_old_yearly.csv",     extract_ths_old_2020_values),
    ("07_ths_old_single_q",   "raw_07_ths_old_single_q.csv",   extract_ths_old_2020_values),
    ("08_ths_new_report",     "raw_08_ths_new_report.csv",     extract_ths_new_2020_values),
    ("09_ths_new_yearly",     "raw_09_ths_new_yearly.csv",     extract_ths_new_2020_values),
    ("10_sina_cf",            "raw_10_sina_cf.csv",            extract_sina_2020_values),
]


def main():
    rds = load_rds()
    rds_items = [it for it in rds["items"] if it["value"] is not None]
    print(f"RDS standard: {len(rds_items)} items with non-null values")

    all_summary = []
    all_details = {}

    for ch_name, csv_file, extractor in CHANNELS:
        csv_path = os.path.join(OUT_DIR, csv_file)
        if not os.path.exists(csv_path):
            print(f"\n[{ch_name}] SKIP: {csv_path} not found")
            continue
        try:
            ch_values = extractor(csv_path)
        except Exception as e:
            print(f"\n[{ch_name}] ERROR extracting: {e}")
            continue

        n_ind, ind_examples = detect_indirect_method(ch_values)
        summary, details = compare_channel(ch_name, ch_values, rds_items)
        summary["indirect_method_keys_found"] = n_ind
        summary["indirect_method_examples"] = ind_examples

        all_summary.append(summary)
        all_details[ch_name] = details
        print(f"\n[{ch_name}]")
        print(f"  渠道字段数(2020年报): {len(ch_values)}")
        print(f"  RDS匹配数(精确到分): {summary['exact_match']}/{summary['rds_items_compared']} = {summary['exact_match_rate']:.1f}%")
        print(f"  精度损失(<1元):     {summary['precision_sub_yuan']}")
        print(f"  四舍五入(<1%):      {summary['rounded_or_aggregated']}")
        print(f"  大误差(>=1%):       {summary['large_error']}")
        print(f"  无匹配:              {summary['no_match']}")
        print(f"  间接法字段数:        {n_ind}")

    # 保存 JSON
    report_path = os.path.join(OUT_DIR, "_quality_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "rds_baseline": {
                "stock_code": rds["stock_code"],
                "report_year": rds["report_year"],
                "item_count": len(rds_items),
            },
            "channels": all_summary,
            "details_per_channel": all_details,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n=== 汇总报告 ===")
    print(f"{'channel':28s} {'fields':>7s} {'exact':>7s} {'<1元':>5s} {'<1%':>5s} {'大误差':>7s} {'无匹配':>7s} {'间接法':>7s}")
    for s in all_summary:
        print(f"{s['channel']:28s} "
              f"{s['channel_value_count']:>7d} "
              f"{s['exact_match']:>7d} "
              f"{s['precision_sub_yuan']:>5d} "
              f"{s['rounded_or_aggregated']:>5d} "
              f"{s['large_error']:>7d} "
              f"{s['no_match']:>7d} "
              f"{s['indirect_method_keys_found']:>7d}")
    print(f"\n报告：{report_path}")


if __name__ == "__main__":
    main()
