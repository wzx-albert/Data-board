# -*- coding: utf-8 -*-
"""
把 Wind 新取到的季度数据合并进 data/source/quarters.json

日常流程：
  1) 助手通过 Wind 取「最近 4 期」而非全部历史（省积分）
  2) 用本脚本并入存量，自动去重、按期对齐、校验长度
  3) python scripts/build_data.py  重新生成页面数据

用法：
  python scripts/merge_quarters.py --data '[{"period":"2026Q3","us_contrib_gov":0.12}]'
  python scripts/merge_quarters.py --file patch.json

  patch 的每条记录：{"period": "2026Q4", "<序列key>": <数值或 null>, ...}
  序列 key：cn_gdp_yoy / us_gdp_saar / us_contrib_pce / us_contrib_inv / us_contrib_gov
"""
import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QSRC = os.path.join(BASE, "data", "source", "quarters.json")
KEYS = ["cn_gdp_yoy", "us_gdp_saar", "us_contrib_pce", "us_contrib_inv", "us_contrib_gov"]


def period_end(period):
    """2026Q4 -> ('2026-12-31', '2026Q4')"""
    p = period.strip().upper()
    if "Q" not in p:
        sys.exit(f"期数格式应为 2026Q4，收到：{period}")
    y, q = p.split("Q")
    q = int(q)
    if q not in (1, 2, 3, 4):
        sys.exit(f"季度取值应为 1-4，收到：{period}")
    m = q * 3
    day = 31 if m in (3, 12) else 30
    return f"{y}-{m:02d}-{day}", f"{y}Q{q}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="JSON 字符串，数组形式")
    ap.add_argument("--file", help="JSON 文件路径")
    ap.add_argument("--dry-run", action="store_true", help="只显示结果不写入")
    a = ap.parse_args()

    if not a.data and not a.file:
        sys.exit("需要 --data 或 --file")
    patch = json.loads(a.data) if a.data else json.load(open(a.file, encoding="utf-8"))
    if isinstance(patch, dict):
        patch = [patch]

    q = json.load(open(QSRC, encoding="utf-8"))
    dates, labels = q["dates"], q["labels"]
    series = {k: list(q["series"][k]["values"]) for k in KEYS}

    for rec in patch:
        period = rec.get("period") or rec.get("label")
        if not period:
            sys.exit(f"记录缺少 period 字段：{rec}")
        d, lab = period_end(period)

        if d in dates:
            i = dates.index(d)
            changed = []
            for k in KEYS:
                if k in rec and rec[k] is not None:
                    series[k][i] = rec[k]
                    changed.append(f"{k}={rec[k]}")
            print(f"[更新] {lab} 已存在，更新 {len(changed)} 个值：" + ", ".join(changed))
        else:
            if d < dates[-1]:
                sys.exit(f"{lab} 早于现有最后一期 {labels[-1]}，不支持中间插入，请人工核对")
            if not _is_next(dates[-1], d):
                sys.exit(f"{lab} 与现有最后一期 {labels[-1]} 不连续，请先补齐中间期")
            dates.append(d)
            labels.append(lab)
            for k in KEYS:
                series[k].append(rec.get(k))
            print(f"[新增] {lab}（{d}），共 {len(dates)} 期")

    # 校验
    for k in KEYS:
        if len(series[k]) != len(dates):
            sys.exit(f"序列 {k} 长度 {len(series[k])} 与期数 {len(dates)} 不一致")
    for i in range(1, len(dates)):
        if dates[i] <= dates[i - 1]:
            sys.exit(f"日期未递增：{dates[i-1]} -> {dates[i]}")

    if a.dry_run:
        print("[dry-run] 未写入")
        return

    q["dates"], q["labels"] = dates, labels
    q["series"] = {k: {"values": series[k]} for k in KEYS}
    json.dump(q, open(QSRC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[写入] {QSRC}  共 {len(dates)} 期，{labels[0]} → {labels[-1]}")
    print("下一步：python scripts/build_data.py")


def _is_next(last_date, new_date):
    """判断 new_date 是否为 last_date 的下一个季度末"""
    from datetime import date
    d = date.fromisoformat(last_date)
    y, m = d.year, d.month
    m += 3
    while m > 12:
        m -= 12
        y += 1
    day = 31 if m in (3, 12) else 30
    return new_date == f"{y}-{m:02d}-{day}"


if __name__ == "__main__":
    main()
