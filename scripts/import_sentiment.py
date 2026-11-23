# -*- coding: utf-8 -*-
"""
把导出的底表（csv / xlsx）转成 data/source/sentiment.json

用法
----
python scripts/import_sentiment.py --file "D:/path/A股情绪底表.xlsx"
python scripts/import_sentiment.py --file "底表.csv" --start 2005-01-01

列名匹配规则：表头里出现下列关键词即认为命中（大小写、空格、括号内容不敏感）
    日期      日期 / 交易日期 / 时间 / date
    成交额    成交额 / 成交金额 / amount
    总市值    总市值
    流通市值  流通市值
    换手率    换手率
    上涨家数  上涨家数
    下跌家数  下跌家数
    市盈率    市盈率 / PE
    市净率    市净率 / PB
    十年国债  10年国债 / 国债收益率 / 10Y
    融资买入  融资买入额
    融资余额  融资余额

数值写法兼容：, 分隔、万亿/亿/万、% / 倍 / 家 / 元 后缀、- 或 -- 表示缺失。
单位约定（写入 sentiment.json 前统一）：
    金额类 → 元；比率类 → %；家数 → 家；估值 → 倍
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "source", "sentiment.json")

ALIASES = {
    "date":         ["日期", "交易日期", "时间", "date"],
    "amount":       ["成交额", "成交金额", "amount"],
    "mktcap_total": ["总市值", "市值合计"],
    "mktcap_float": ["流通市值"],
    "turnover":     ["换手率"],
    "adv":          ["上涨家数", "上涨数量"],
    "dec":          ["下跌家数", "下跌数量"],
    "pe":           ["市盈率", "pe_ttm", "pe"],
    "pb":           ["市净率", "pb"],
    "y10":          ["10年国债", "十年国债", "国债收益率", "10y"],
    "margin_buy":   ["融资买入额", "融资买入"],
    "margin_bal":   ["融资余额"],
}

MULT = [("万亿", 1e12), ("亿", 1e8), ("万", 1e4)]


def to_num(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace(",", "").replace("，", "").replace(" ", "")
    if t in ("", "-", "--", "—", "nan", "None", "null"):
        return None
    for suf, m in MULT:
        if t.endswith(suf):
            try:
                return float(t[: -len(suf)]) * m
            except ValueError:
                return None
    t = re.sub(r"[%倍家元年]$", "", t)
    try:
        return float(t)
    except ValueError:
        return None


def norm_date(s):
    if s is None:
        return None
    if isinstance(s, datetime):
        return s.strftime("%Y-%m-%d")
    if isinstance(s, date):
        return s.isoformat()
    t = str(s).strip()
    m = re.search(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", t)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{4})(\d{2})(\d{2})", t)
    if m:
        return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))
    return None


def match_col(header, key):
    h = str(header).lower().replace(" ", "")
    for a in ALIASES[key]:
        if a.lower() in h:
            return True
    return False


def read_rows(path):
    """返回 (headers, rows)；支持 csv 与 xlsx"""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            sys.exit("读取 xlsx 需要 openpyxl：pip install openpyxl")
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb[wb.sheetnames[0]]
        data = [list(r) for r in ws.iter_rows(values_only=True)]
    else:
        for enc in ("utf-8-sig", "gbk", "utf-8"):
            try:
                with open(path, encoding=enc, newline="") as f:
                    data = [r for r in csv.reader(f)]
                break
            except UnicodeDecodeError:
                continue
        else:
            sys.exit("无法识别文件编码")

    # 找表头行：前 10 行里第一行能匹配到「日期」的
    hi = 0
    for i, row in enumerate(data[:10]):
        if any(norm_date(c) for c in row[:3]) and any(match_col(c, "date") for c in row):
            hi = i
            break
        if any(match_col(c, "date") for c in row):
            hi = i
            break
    headers = [str(c) if c is not None else "" for c in data[hi]]
    return headers, data[hi + 1:]


def build(path, start=None, source=""):
    headers, rows = read_rows(path)
    idx = {}
    for i, h in enumerate(headers):
        for k in ALIASES:
            if k not in idx and match_col(h, k):
                idx[k] = i
    if "date" not in idx:
        sys.exit(f"没找到日期列。表头：{headers[:12]}")

    missing = [k for k in ALIASES if k != "date" and k not in idx]
    if missing:
        print(f"[warn] 未匹配到列：{missing}（对应指标将留空）")

    rec = {k: [] for k in ALIASES if k != "date"}
    dates = []
    for row in rows:
        if not row:
            continue
        d = norm_date(row[idx["date"]] if idx["date"] < len(row) else None)
        if not d:
            continue
        if start and d < start:
            continue
        dates.append(d)
        for k in rec:
            i = idx.get(k)
            rec[k].append(to_num(row[i]) if (i is not None and i < len(row)) else None)

    if not dates:
        sys.exit("没有解析出任何数据行")

    order = sorted(range(len(dates)), key=lambda i: dates[i])
    dates = [dates[i] for i in order]
    for k in rec:
        rec[k] = [rec[k][i] for i in order]

    dup = len(dates) - len(set(dates))
    if dup:
        seen, dd, rr = set(), [], {k: [] for k in rec}
        for i, d in enumerate(dates):
            if d in seen:
                continue
            seen.add(d)
            dd.append(d)
            for k in rec:
                rr[k].append(rec[k][i])
        print(f"[warn] 去重 {dup} 行")
        dates, rec = dd, rr

    payload = {
        "meta": {
            "source": source or os.path.basename(path),
            "importedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "start": dates[0], "end": dates[-1],
            "columns": {k: (idx.get(k) is not None) for k in rec},
        },
        "dates": dates,
        "raw": rec,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[ok] {OUT}  {len(dates)} 行  {dates[0]} → {dates[-1]}")
    for k in rec:
        n = sum(1 for v in rec[k] if v is not None)
        print(f"  {k:14s} 有效 {n}/{len(dates)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--start", default=None, help="起始日期，如 2005-01-01")
    ap.add_argument("--source", default="", help="数据来源说明")
    a = ap.parse_args()
    if not os.path.exists(a.file):
        sys.exit(f"文件不存在：{a.file}")
    build(a.file, a.start, a.source)
