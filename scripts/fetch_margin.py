# -*- coding: utf-8 -*-
"""抓取东方财富两融历史数据（融资余额、融资买入额、占流通市值比）

输出 data/source/margin.json
    {"meta": {...}, "rows": [{"date","rzye","rzmre","rzyezb","ltsz"}, ...]}
"""
import json
import os
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "source", "margin.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
API = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def page(p, size=500):
    q = {
        "reportName": "RPTA_RZRQ_LSHJ",
        "columns": "DIM_DATE,RZYE,RZMRE,RZYEZB,LTSZ",
        "pageNumber": str(p),
        "pageSize": str(size),
        "sortColumns": "DIM_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    url = API + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    rows, p = [], 1
    while True:
        d = page(p)
        if not d.get("success"):
            print("第 %d 页失败: %s" % (p, d.get("message")))
            break
        data = (d.get("result") or {}).get("data") or []
        if not data:
            break
        for it in data:
            rows.append({
                "date": it["DIM_DATE"][:10],
                "rzye": it.get("RZYE"),
                "rzmre": it.get("RZMRE"),
                "rzyezb": it.get("RZYEZB"),
                "ltsz": it.get("LTSZ"),
            })
        print("  第 %d 页 %d 条，累计 %d" % (p, len(data), len(rows)), flush=True)
        pages = (d.get("result") or {}).get("pages") or 0
        if p >= pages:
            break
        p += 1
        time.sleep(0.3)

    rows.sort(key=lambda x: x["date"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"meta": {"source": "东方财富 数据中心 · 沪深两市两融历史(RPTA_RZRQ_LSHJ)",
                        "start": rows[0]["date"] if rows else "",
                        "end": rows[-1]["date"] if rows else "",
                        "count": len(rows)},
               "rows": rows},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("已写出 %s  共 %d 条  %s → %s" % (OUT, len(rows),
          rows[0]["date"] if rows else "-", rows[-1]["date"] if rows else "-"))


if __name__ == "__main__":
    main()
