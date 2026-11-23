# -*- coding: utf-8 -*-
"""用 WindPy 取美国 GDP 分项 G 代码，对齐 quarters.json 并更新"""
import json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QSRC = os.path.join(BASE, "data", "source", "quarters.json")

sys.path.insert(0, r"D:\Wind\Wind.NET.Client\WindNET\x64")
from WindPy import w


def fetch(code, begin, end):
    r = w.edb(code, begin, end, "Fill=Previous")
    if r.ErrorCode != 0:
        sys.exit(f"{code} 取数失败 ErrorCode={r.ErrorCode}")
    out = {}
    for t, v in zip(r.Times, r.Data[0]):
        out[t.strftime("%Y-%m-%d")] = v
    return out


def main():
    w.start()
    if not w.isconnected():
        sys.exit("WindPy 未连接")

    q = json.load(open(QSRC, encoding="utf-8"))
    dates = q["dates"]

    # 取两个待补字段的完整历史（对齐 63 期）
    gov = fetch("G0001791", dates[0], dates[-1])   # 政府支出拉动
    net = fetch("G0001784", dates[0], dates[-1])   # 净出口拉动（官方）

    print("quarters.json 期数:", len(dates), dates[0], "->", dates[-1])
    for name, m in [("G0001791 gov", gov), ("G0001784 net", net)]:
        miss = [d for d in dates if d not in m]
        print(f"  {name}: 取到 {len(m)} 点，季度日期缺失 {len(miss)} 个", miss[:5])

    # 对齐
    gov_vals = [gov.get(d) for d in dates]
    net_vals = [net.get(d) for d in dates]
    print("  末5期 gov:", [(d, round(v, 2)) for d, v in zip(dates[-5:], gov_vals[-5:])])
    print("  末5期 net:", [(d, round(v, 2)) for d, v in zip(dates[-5:], net_vals[-5:])])

    q["series"]["us_contrib_gov"]["values"] = gov_vals
    q["series"]["us_contrib_net"]["values"] = net_vals
    q["pending"] = {
        "status": "已补齐",
        "note": "2026-11-23 WindPy(edb) 取 G0001791/G0001784 官方值，替换残差估算与旧代码 G1140985",
    }

    json.dump(q, open(QSRC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[写入] quarters.json 完成，pending 已清空")
    print("下一步：python scripts/build_data.py")


if __name__ == "__main__":
    main()
