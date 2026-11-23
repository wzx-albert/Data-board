# -*- coding: utf-8 -*-
"""
构建 data/sentiment-data.js（A 股情绪板块数据）

原料：data/source/sentiment.json
    {
      "meta": {"source": "...", "start": "2005-01-04", "end": "..."},
      "dates": ["2005-01-04", ...],                  # 交易日，升序
      "raw": {
        "amount":        [...],   # A股成交额（元）
        "mktcap_total":  [...],   # A股总市值（元）
        "mktcap_float":  [...],   # A股流通市值（元）
        "turnover":      [...],   # 换手率（%，可直接给，也可为空由脚本算）
        "adv":           [...],   # 上涨家数
        "dec":           [...],   # 下跌家数
        "pe":            [...],   # 全A 市盈率 TTM（倍）
        "pb":            [...],   # 全A 市净率（倍）
        "y10":           [...],   # 10 年期国债收益率（%）
        "margin_buy":    [...],   # 融资买入额（元）
        "margin_bal":    [...]    # 融资余额（元）
      }
    }

输出 data/sentiment-data.js:
    window.SENTIMENT_DATA = { meta, dates, series{key: {label,unit,values,pctl,...}}, summary }

分位口径：全历史分位（自数据起点，扩展窗口），0-100。
用法：
    python scripts/build_sentiment.py           # 读真实原料
    python scripts/build_sentiment.py --demo    # 原料缺失时生成占位序列（页面上会标注示例）
"""
import argparse
import bisect
import json
import math
import os
import random
import re
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "sentiment-data.js")
SRC = os.path.join(BASE, "data", "source", "sentiment.json")

# 指标定义：key, 名称, 单位, 维度, 小数位, 是否反向（分位越高代表情绪越低）
SPECS = [
    ("sent_amt_cap",  "成交额 / 总市值",       "%",  "量",   2, False),
    ("sent_turnover", "换手率",                "%",  "量",   2, False),
    ("sent_advance",  "上涨家数占比",          "%",  "价",   1, False),
    ("sent_mbuy",     "融资买入 / 成交额",     "%",  "资金", 2, False),
    ("sent_mbal",     "融资余额 / 总市值",     "%",  "资金", 2, False),
    ("sent_pe",       "全A 市盈率 TTM",        "倍", "估值", 2, False),
    ("sent_pb",       "全A 市净率",            "倍", "估值", 2, False),
    ("sent_erp",      "EP − 10Y 国债",         "%",  "风险溢价", 2, True),
]


# ------------------------------ 工具 ------------------------------
def pct_series(values):
    """全历史扩展窗口分位：每个点在有史以来的百分位（0-100）"""
    out, book = [], []
    for v in values:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append(None)
            continue
        bisect.insort(book, v)
        pos = bisect.bisect_right(book, v)
        out.append(round(pos / len(book) * 100, 1))
    return out


def div(a, b, scale=1.0, digits=4):
    if a is None or b in (None, 0):
        return None
    try:
        return round(a / b * scale, digits)
    except Exception:
        return None


def safe_get(d, k, n):
    v = d.get(k)
    if not isinstance(v, list):
        return [None] * n
    if len(v) < n:
        return list(v) + [None] * (n - len(v))
    return v[:n]


# ------------------------------ 演示数据 ------------------------------
def demo_source(n_years=21):
    """生成 2005-2026 的占位序列，仅用于页面评审，页面上会明确标注"""
    rnd = random.Random(20261120)
    start = date(2005, 1, 4)
    end = date(2026, 11, 20)
    days, cur = [], start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur.isoformat())
        cur += timedelta(days=1)
    n = len(days)

    # 用几条慢周期正弦 + 噪声模拟牛熊
    def wave(i, period, amp, base, phase=0.0):
        return base + amp * math.sin(2 * math.pi * i / period + phase)

    amount, cap_t, cap_f, turn, adv, dec, pe, pb, y10, mbuy, mbal = ([] for _ in range(11))
    pe_v, pb_v = 22.0, 2.2
    cap = 3.0e12
    for i in range(n):
        cycle = wave(i, 1450, 0.55, 1.0) + wave(i, 320, 0.12, 0.0, 1.2)
        cycle = max(0.35, cycle + rnd.gauss(0, 0.03))
        cap = cap * (1 + 0.00055 * (cycle - 1) * 6 + rnd.gauss(0, 0.006))
        tr = max(0.7, wave(i, 900, 1.1, 2.1) * (0.6 + 0.7 * cycle) + rnd.gauss(0, 0.22))
        amt = cap * tr / 100 * rnd.uniform(0.92, 1.08)
        pe_v = max(11.0, min(78.0, pe_v * (1 + 0.0009 * (cycle - 1) * 8) + rnd.gauss(0, 0.05)))
        pb_v = max(1.2, min(7.5, pb_v * (1 + 0.0008 * (cycle - 1) * 8) + rnd.gauss(0, 0.008)))
        yld = max(1.6, min(5.2, wave(i, 2100, 1.0, 3.3, 2.0) + rnd.gauss(0, 0.015)))
        pct_up = max(0.03, min(0.97, 0.5 + 0.34 * (cycle - 1) * 1.6 + rnd.gauss(0, 0.09)))
        total = 5200
        up = int(total * pct_up)
        amount.append(amt)
        cap_t.append(cap)
        cap_f.append(cap * 0.78)
        turn.append(amt / (cap * 0.78) * 100)
        adv.append(up)
        dec.append(total - up)
        pe.append(pe_v)
        pb.append(pb_v)
        y10.append(yld)
        mbuy.append(amt * max(0.02, min(0.16, 0.055 + 0.05 * (cycle - 1))) * rnd.uniform(0.9, 1.1))
        mbal.append(cap * max(0.005, min(0.055, 0.016 + 0.014 * (cycle - 1))) * rnd.uniform(0.95, 1.05))

    return {
        "meta": {"source": "占位序列（demo）", "start": days[0], "end": days[-1], "demo": True},
        "dates": days,
        "raw": {
            "amount": amount, "mktcap_total": cap_t, "mktcap_float": cap_f,
            "turnover": turn, "adv": adv, "dec": dec, "pe": pe, "pb": pb,
            "y10": y10, "margin_buy": mbuy, "margin_bal": mbal,
        },
    }


# ------------------------------ 主流程 ------------------------------
def build(src, demo=False):
    dates = src["dates"]
    n = len(dates)
    raw = src.get("raw") or {}
    g = lambda k: safe_get(raw, k, n)

    amount, cap_t, cap_f = g("amount"), g("mktcap_total"), g("mktcap_float")
    turn_in, adv, dec = g("turnover"), g("adv"), g("dec")
    pe, pb, y10 = g("pe"), g("pb"), g("y10")
    mbuy, mbal = g("margin_buy"), g("margin_bal")

    # 衍生指标
    amt_cap = [div(amount[i], cap_t[i], 100) for i in range(n)]

    turnover = []
    for i in range(n):
        if turn_in[i] not in (None, 0):
            turnover.append(round(turn_in[i], 4))
        else:
            turnover.append(div(amount[i], cap_f[i], 100))

    advance = []
    for i in range(n):
        a, d = adv[i], dec[i]
        advance.append(round(a / (a + d) * 100, 2) if (a is not None and d is not None and (a + d) > 0) else None)

    mbuy_r = [div(mbuy[i], amount[i], 100) for i in range(n)]
    mbal_r = [div(mbal[i], cap_t[i], 100) for i in range(n)]

    # EP − 10Y：EP = 100 / PE，与国债收益率同为百分数，直接相减
    erp = []
    for i in range(n):
        if pe[i] in (None, 0) or y10[i] is None:
            erp.append(None)
        else:
            erp.append(round(100.0 / pe[i] - y10[i], 3))

    values = {
        "sent_amt_cap": amt_cap, "sent_turnover": turnover, "sent_advance": advance,
        "sent_mbuy": mbuy_r, "sent_mbal": mbal_r, "sent_pe": pe, "sent_pb": pb, "sent_erp": erp,
    }

    series = {}
    items = []
    pcts_for_avg = []
    for key, label, unit, group, digits, invert in SPECS:
        vals = values[key]
        vals = [round(v, 4) if isinstance(v, (int, float)) else v for v in vals]
        values[key] = vals
        pctl = pct_series(vals)
        series[key] = {
            "label": label, "unit": unit, "group": group, "digits": digits,
            "invert": invert, "values": vals, "pctl": pctl,
        }
        # 汇总用最后一个有效点
        last_v = last_p = None
        for i in range(n - 1, -1, -1):
            if vals[i] is not None and pctl[i] is not None:
                last_v, last_p = vals[i], pctl[i]
                break
        items.append({"key": key, "label": label, "unit": unit, "group": group,
                      "digits": digits, "value": last_v, "pctl": last_p})
        if last_p is not None:
            pcts_for_avg.append(100 - last_p if invert else last_p)

    avg = round(sum(pcts_for_avg) / len(pcts_for_avg), 1) if pcts_for_avg else None

    payload = {
        "meta": {
            "generatedAt": date.today().isoformat(),
            "demo": bool(src.get("meta", {}).get("demo")),
            "source": src.get("meta", {}).get("source", ""),
            "start": dates[0] if n else "",
            "end": dates[-1] if n else "",
            "count": n,
            "windowNote": "分位为全历史分位（自数据起点，扩展窗口）",
        },
        "dates": dates,
        "series": series,
        "summary": {"avg": avg, "items": items},
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.SENTIMENT_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"[out] {OUT}  {os.path.getsize(OUT)/1024:.1f} KB  {n} 点 {dates[0]} → {dates[-1]}")
    print(f"[summary] 情绪温度（分位均值）= {avg}")
    for it in items:
        print(f"  {it['label']:16s} {it['value']:>10} {it['unit']:<2s} 分位 {it['pctl']}")
    bump_cache()


def bump_cache():
    idx = os.path.join(BASE, "index.html")
    if not os.path.exists(idx):
        return
    html = open(idx, encoding="utf-8").read()
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new, n = re.subn(r"(data/sentiment-data\.js\?v=)[\w\.\-]+", r"\g<1>" + stamp, html)
    if n == 0:
        new, n = re.subn(r'(src="data/sentiment-data\.js)"', r'\g<1>?v=' + stamp + '"', html)
    if n:
        open(idx, "w", encoding="utf-8").write(new)
        print(f"[cache] index.html 情绪数据版本号 -> {stamp}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="原料缺失时用占位序列")
    a = ap.parse_args()

    if os.path.exists(SRC):
        build(json.load(open(SRC, encoding="utf-8")))
    elif a.demo:
        print("[demo] 未找到 data/source/sentiment.json，使用占位序列")
        build(demo_source(), demo=True)
    else:
        raise SystemExit(f"缺少原料文件：{SRC}\n（可加 --demo 生成占位序列先看页面）")
