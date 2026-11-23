# -*- coding: utf-8 -*-
"""通过 Excel + Wind 插件批量取数（WSD/EDB 公式）

用法:
    python scripts/wind_fetch.py probe            # 权限探测（短区间）
    python scripts/wind_fetch.py run <config.json> <out.json>
"""
import sys, json, time, datetime
import win32com.client as win32

# 探测清单: (标签, 函数, 代码, 字段)
PROBE = [
    ("全A收盘", "WSD", "881001.WI", "close"),
    ("全A成交额", "WSD", "881001.WI", "amt"),
    ("全A换手率", "WSD", "881001.WI", "turn"),
    ("全A_PE_TTM", "WSD", "881001.WI", "pe_ttm"),
    ("全A_PB", "WSD", "881001.WI", "pb_lf"),
    ("中债国债1Y", "EDB", "S0059744", ""),
    ("中债国债10Y", "EDB", "S0059749", ""),
    ("中票AA+3Y", "EDB", "S0059724", ""),
    ("两融余额", "EDB", "M0021386", ""),
]


def formula(func, code, field, start, end, options=None):
    if func == "EDB":
        # EDB 第 4 个参数不能传空串，否则 #VALUE!
        return '=EDB("%s","%s","%s","%s")' % (code, start, end, options or "unit=1")
    return '=WSD("%s","%s","%s","%s","%s")' % (code, field, start, end, options or "")


def span_rows(start, end):
    """按日期跨度估算需要的行数（交易日占约 68%）"""
    d0 = datetime.date.fromisoformat(start)
    d1 = datetime.date.fromisoformat(end)
    return min(7000, max(200, int((d1 - d0).days * 0.72) + 60))


def to_date(v):
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and 20000 < v < 80000:
        return (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=v)).strftime("%Y-%m-%d")
    return str(v)[:10]


def read_block(ws):
    """读 A/B 两列，返回 [(date, value)]"""
    ur = ws.UsedRange
    n = ur.Rows.Count
    if n < 1:
        return []
    vals = ur.Value
    if vals is None:
        return []
    if not isinstance(vals, (list, tuple)):
        return []
    if len(vals) == 2 and not isinstance(vals[0], (list, tuple)):
        vals = [vals]          # 单行时 Value 直接是 (d, v)
    out = []
    for row in vals:
        if row[0] is None or row[1] is None:
            continue
        out.append((to_date(row[0]), row[1]))
    return out


BLOCK = 400   # 默认预留行数（run_jobs 里会按日期跨度放大）


def read_at(ws, r0, block=None):
    """从 r0 行起读 block 行的 A/B 两列，返回 [(date, value)]"""
    block = block or BLOCK
    vals = ws.Range("A%d:B%d" % (r0, r0 + block - 1)).Value
    if vals is None:
        return []
    if not isinstance(vals, (list, tuple)):
        return []
    if len(vals) == 2 and not isinstance(vals[0], (list, tuple)):
        vals = [vals]
    out = []
    for row in vals:
        if row[0] is None or row[1] is None:
            continue
        if isinstance(row[1], str):
            continue          # #VALUE! 等错误值
        out.append((to_date(row[0]), row[1]))
    return out


def run_jobs(jobs, wait=180):
    """jobs: [(label, func, code, field, start, end)] -> {label: [(date,val)]}"""
    app = win32.DispatchEx("Excel.Application")
    app.Visible = True
    app.DisplayAlerts = False
    app.AskToUpdateLinks = False
    app.ScreenUpdating = False
    wb = app.Workbooks.Add()
    ws = wb.Worksheets(1)
    ws.Name = "wind"
    try:
        rows = {}
        blocks = {}
        cursor = 1
        for job in jobs:
            label, func, code, field, start, end = job
            blocks[label] = span_rows(start, end) + 20
            rows[label] = cursor
            ws.Cells(cursor, 1).Formula = formula(func, code, field, start, end)
            cursor += blocks[label]

        app.CalculateFullRebuild()

        result = {}
        deadline = time.time() + wait
        pending = [j[0] for j in jobs]
        while pending and time.time() < deadline:
            time.sleep(3)
            for label in list(pending):
                got = read_at(ws, rows[label], blocks[label])
                if got:
                    result[label] = got
                    pending.remove(label)
            if pending:
                print("  等待中: %s" % ", ".join(pending), flush=True)

        for job in jobs:
            label = job[0]
            n = len(result.get(label, []))
            if n:
                first, last = result[label][0], result[label][-1]
                print("  %-12s %-10s 点数=%5d   %s=%s   %s=%s" % (
                    label, job[2], n, first[0], round(first[1], 4), last[0], round(last[1], 4)))
            else:
                err = ws.Cells(rows[label], 1).Value
                print("  %-12s %-10s 未取到  (单元格=%s)" % (label, job[2], str(err)[:30]))
        return result
    finally:
        wb.Close(SaveChanges=False)
        app.Quit()


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "probe":
        jobs = [(l, f, c, fl, "2026-10-01", "2026-11-21") for l, f, c, fl in PROBE]
        print("权限探测（2026-10-01 ~ 2026-11-21）")
        run_jobs(jobs, wait=150)
    elif len(sys.argv) >= 4 and sys.argv[1] == "run":
        cfg = json.load(open(sys.argv[2], encoding="utf-8"))
        jobs = [(j["label"], j.get("func", "WSD"), j["code"], j.get("field", ""),
                 j["start"], j["end"]) for j in cfg["jobs"]]
        res = run_jobs(jobs, wait=cfg.get("wait", 300))
        json.dump({k: v for k, v in res.items()}, open(sys.argv[3], "w", encoding="utf-8"),
                  ensure_ascii=False)
        print("已写出", sys.argv[3], "序列数=", len(res))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
