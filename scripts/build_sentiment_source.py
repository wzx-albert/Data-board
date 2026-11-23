# -*- coding: utf-8 -*-
"""组装 data/source/sentiment.json（A股情绪原料）

输入：
    data/source/wind_core.json   Wind Excel 插件取回的 881001.WI 序列
    data/source/margin.json      东方财富两融历史
输出：
    data/source/sentiment.json   供 build_sentiment.py 使用

缺项（暂无稳定来源）在 raw 里留空，build 时会输出 null：
    mktcap_total  A股总市值
    adv / dec     上涨 / 下跌家数
    y10           10 年期国债收益率
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE, "data", "source")
OUT = os.path.join(SRC_DIR, "sentiment.json")


def load(name):
    p = os.path.join(SRC_DIR, name)
    if not os.path.exists(p):
        raise SystemExit("缺少 %s" % p)
    return json.load(open(p, encoding="utf-8"))


def main():
    wind = load("wind_core.json")["series"]
    bond = load("bond.json")["series"]
    margin = load("margin.json")

    # 以 Wind 交易日为主轴
    dates = [d for d, _ in wind["amount"]]
    n = len(dates)

    def pick(key):
        return [v for _, v in wind[key]] if key in wind else [None] * n

    mg = {r["date"]: r for r in margin["rows"]}
    bd = {d: v for d, v in bond["y10"]} if "y10" in bond else {}

    def r(v, nd=2):
        return None if v is None else round(v, nd)

    def r0(v):
        return None if v is None else round(v)

    raw = {
        "amount": [r0(v) for v in pick("amount")],                 # 元
        "mktcap_total": [None] * n,                                # 待补：A股总市值
        "mktcap_float": [r0(v) for v in pick("mktcap_float")],     # 元
        "turnover": [r(v, 4) for v in pick("turnover")],           # %
        "adv": [None] * n,                                         # 待补：上涨家数
        "dec": [None] * n,                                         # 待补：下跌家数
        "pe": [r(v, 4) for v in pick("pe")],
        "pb": [r(v, 4) for v in pick("pb")],
        "y10": [r(bd.get(d), 4) for d in dates],                   # 10Y 国债收益率（%）
        "margin_buy": [r0(mg[d]["rzmre"]) if d in mg else None for d in dates],
        "margin_bal": [r0(mg[d]["rzye"]) if d in mg else None for d in dates],
        "margin_bal_float_ratio": [r(mg[d]["rzyezb"], 4) if d in mg else None for d in dates],
    }

    payload = {
        "meta": {
            "source": "Wind 881001.WI（Excel WSD 插件）+ 东方财富两融",
            "start": dates[0], "end": dates[-1], "count": n,
            "missing": ["mktcap_total", "adv", "dec"],
        },
        "dates": dates,
        "raw": raw,
    }
    json.dump(payload, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("已写出 %s  %d 点  %s → %s" % (OUT, n, dates[0], dates[-1]))
    filled = [(k, sum(1 for v in vs if v is not None)) for k, vs in raw.items()]
    for k, c in filled:
        print("  %-22s 有效 %d" % (k, c))


if __name__ == "__main__":
    main()
