# -*- coding: utf-8 -*-
"""
构建 data/market-data.js

数据来源与更新方式
------------------
1) 季度序列（中国 GDP、美国 GDP 及分项）
   存量在 data/source/quarters.json，脚本只读取、不联网。
   新增季度时，由助手通过 Wind 取最近几期后追加到该文件（labels / values 需等长），
   再运行本脚本即可，无需重取历史。

2) 10Y 美债收益率
   东方财富公开接口，默认“增量模式”：从本地已有数据的最后日期往前 10 天开始拉，
   与旧数据合并去重。日常更新通常只拉回十几个点，不产生 Wind 积分消耗。

用法
----
python scripts/build_data.py            # 增量更新（推荐，默认）
python scripts/build_data.py --full     # 全量重拉美债（换数据源、修复历史时用）
python scripts/build_data.py --check    # 只校验数据一致性，不联网不写文件
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "market-data.js")
QSRC = os.path.join(BASE, "data", "source", "quarters.json")
US10Y_BEGIN = "2010-01-01"
LOOKBACK_DAYS = 10


# ----------------------------- 读取本地存量 -----------------------------
def load_existing():
    if not os.path.exists(OUT):
        return None
    raw = open(OUT, encoding="utf-8").read()
    if "window.MARKET_DATA = " not in raw:
        return None
    body = raw.split("window.MARKET_DATA = ", 1)[1].rstrip().rstrip(";")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def load_quarters():
    if not os.path.exists(QSRC):
        sys.exit(f"缺少季度存量文件：{QSRC}")
    return json.load(open(QSRC, encoding="utf-8"))


def check_quarters(q):
    dates, labels = q["dates"], q["labels"]
    if len(dates) != len(labels):
        sys.exit(f"季度 dates({len(dates)}) 与 labels({len(labels)}) 长度不一致")
    for k, v in q["series"].items():
        vals = v["values"]
        if len(vals) != len(dates):
            sys.exit(f"序列 {k} 长度 {len(vals)} 与期数 {len(dates)} 不一致")
    # 日期必须严格递增
    for i in range(1, len(dates)):
        if dates[i] <= dates[i - 1]:
            sys.exit(f"季度日期未递增：{dates[i-1]} -> {dates[i]}")
    return True


# ------------------------------ 美债数据 ------------------------------
def fetch_us10y(begin, page_size=500):
    rows, page = [], 1
    while True:
        url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
               "reportName=RPTA_WEB_TREASURYYIELD&columns=ALL"
               f"&pageNumber={page}&pageSize={page_size}"
               "&sortColumns=SOLAR_DATE&sortTypes=1"
               f"&filter=(SOLAR_DATE%3E%3D%27{begin}%27)")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            js = json.loads(r.read().decode("utf-8"))
        data = (js.get("result") or {}).get("data") or []
        if not data:
            break
        for d in data:
            v = d.get("EMG00001310")
            if v is not None:
                rows.append([d["SOLAR_DATE"][:10], v])
        if len(data) < page_size:
            break
        page += 1
    rows.sort(key=lambda x: x[0])
    return rows


def merge_us10y(old_pairs, new_pairs):
    """按日期合并，新值覆盖旧值"""
    book = {d: v for d, v in old_pairs}
    added = 0
    for d, v in new_pairs:
        if d not in book:
            added += 1
        book[d] = v
    dates = sorted(book)
    return [[d, book[d]] for d in dates], added


def bump_cache_version():
    """改写 index.html 里 market-data.js 的版本号，确保浏览器不会拿缓存里的旧数据"""
    idx = os.path.join(BASE, "index.html")
    if not os.path.exists(idx):
        return
    html = open(idx, encoding="utf-8").read()
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new, n = re.subn(r"(data/market-data\.js\?v=)[\w\.\-]+", r"\g<1>" + stamp, html)
    if n == 0:
        new, n = re.subn(r'(src="data/market-data\.js)"', r'\g<1>?v=' + stamp + '"', html)
    if n:
        open(idx, "w", encoding="utf-8").write(new)
        print(f"[cache] index.html 数据版本号 -> {stamp}")


# -------------------------------- 主流程 --------------------------------
def build(full=False, check_only=False):
    q = load_quarters()
    check_quarters(q)
    qdates, qlabels = q["dates"], q["labels"]
    sv = {k: v["values"] for k, v in q["series"].items()}

    # 净出口：优先用官方值（G0001784），缺失期用残差兜底（GDP - 消费 - 投资 - 政府）
    net = []
    official_net = sv.get("us_contrib_net", [])
    for i in range(len(qdates)):
        v = official_net[i] if i < len(official_net) else None
        if v is None:
            parts = [sv["us_gdp_saar"][i], sv["us_contrib_pce"][i],
                     sv["us_contrib_inv"][i], sv["us_contrib_gov"][i]]
            v = None if any(p is None for p in parts) else round(parts[0] - sum(parts[1:]), 2)
        net.append(v)
    sv["us_contrib_net"] = net

    if check_only:
        print(f"[check] 季度 {len(qdates)} 期：{qdates[0]} → {qdates[-1]}，各序列等长 ✓")
        ex = load_existing()
        if ex and "us10y_yield" in ex["series"]:
            s = ex["series"]["us10y_yield"]
            print(f"[check] 美债 {len(s['dates'])} 点：{s['dates'][0]} → {s['dates'][-1]}")
        return

    existing = None if full else load_existing()
    old_pairs = []
    if existing and "us10y_yield" in existing.get("series", {}):
        s = existing["series"]["us10y_yield"]
        old_pairs = list(zip(s["dates"], s["values"]))

    if old_pairs:
        begin = (date.fromisoformat(old_pairs[-1][0]) - timedelta(days=LOOKBACK_DAYS)).isoformat()
        mode = f"增量（自 {begin}，已有 {len(old_pairs)} 点）"
    else:
        begin = US10Y_BEGIN
        mode = f"全量（自 {begin}）"

    print(f"[us10y] {mode} …")
    fresh = fetch_us10y(begin)
    merged, added = merge_us10y(old_pairs, fresh)
    print(f"[us10y] 拉回 {len(fresh)} 点，新增 {added} 点，合计 {len(merged)} 点")

    payload = {
        "meta": {
            "generatedAt": date.today().isoformat(),
            "note": "季度数据来自 data/source/quarters.json（Wind EDB）；10Y 美债来自东方财富公开数据（美国财政部口径）",
        },
        "series": {
            "cn_gdp_yoy": {
                "title": "中国 GDP 不变价当季同比", "unit": "%", "freq": "Q",
                "source": "国家统计局 / Wind EDB（M0039354）",
                "dates": qdates, "labels": qlabels, "values": sv["cn_gdp_yoy"],
            },
            "us_gdp_saar": {
                "title": "美国实际 GDP 季调环比折年率", "unit": "%", "freq": "Q",
                "source": "美国经济分析局 / Wind EDB（G0000002）",
                "dates": qdates, "labels": qlabels, "values": sv["us_gdp_saar"],
            },
            "us_contrib_pce": {
                "title": "个人消费支出拉动", "unit": "pct", "freq": "Q",
                "source": "BEA / Wind EDB（G0001773）",
                "dates": qdates, "labels": qlabels, "values": sv["us_contrib_pce"],
            },
            "us_contrib_inv": {
                "title": "国内私人投资拉动", "unit": "pct", "freq": "Q",
                "source": "BEA / Wind EDB（G0001777）",
                "dates": qdates, "labels": qlabels, "values": sv["us_contrib_inv"],
            },
            "us_contrib_gov": {
                "title": "政府支出拉动", "unit": "pct", "freq": "Q",
                "source": "BEA / Wind EDB（G1140985；待换 G0001791 补齐 2026Q3）",
                "dates": qdates, "labels": qlabels, "values": sv["us_contrib_gov"],
            },
            "us_contrib_net": {
                "title": "净出口拉动", "unit": "pct", "freq": "Q",
                "source": "残差估算（待换 Wind G0001784 官方值）",
                "dates": qdates, "labels": qlabels, "values": sv["us_contrib_net"],
            },
            "us10y_yield": {
                "title": "美国 10 年期国债收益率", "unit": "%", "freq": "D",
                "source": "美国财政部 / 东方财富",
                "dates": [r[0] for r in merged], "values": [r[1] for r in merged],
            },
        },
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.MARKET_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"[out] {OUT}  {os.path.getsize(OUT)} bytes")
    bump_cache_version()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="全量重拉美债")
    ap.add_argument("--check", action="store_true", help="只校验不写文件")
    a = ap.parse_args()
    build(full=a.full, check_only=a.check)
