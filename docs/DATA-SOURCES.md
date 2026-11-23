# 数据来源与取数通道

## 1. 三条取数通道（2026-11-23 实测）

| 通道 | 状态 | 可取内容 | 备注 |
|---|---|---|---|
| Wind 终端 Excel 插件（WSD） | ✅ 可用 | 行情、估值、市值、成交额、换手率、中债收益率 | `scripts/wind_fetch.py`，需 Wind 终端登录并开着 |
| Wind Python 接口（WindPy） | ✅ 可用 | EDB 宏观指标（`w.edb()`）、行情 | 需先跑终端「量化接口修复工具」配好 Python 接口，否则 `w.start()` 返回 -2 |
| Wind Excel 插件（EDB 公式） | ❌ 不可用 | — | 程序写 `=EDB()` 返回 `#VALUE!`（走批注协议）；宏观数据改用 WindPy `w.edb()` |

东财公开接口（`datacenter-web.eastmoney.com`）可作为补充，两融历史即由此获取。

## 2. Wind Excel 插件用法

前提：Wind 金融终端已登录并保持运行（Excel 的 WDF.Addin 加载项开机加载，见注册表 `HKLM\SOFTWARE\Microsoft\Office\Excel\Addins\WDF.Addin`）。

```bash
# 权限探测（短区间，看哪些代码/字段能取）
python scripts/wind_fetch.py probe

# 按配置批量取数，输出 JSON
python scripts/wind_fetch.py run config.json out.json
```

配置文件格式：

```json
{
  "wait": 300,
  "jobs": [
    {"label": "amount", "func": "WSD", "code": "881001.WI", "field": "amt",
     "start": "2005-01-01", "end": "2026-11-21"}
  ]
}
```

要点（都是踩过的坑）：

- 每个序列必须**独占一段行区间**（脚本按日期跨度预留，默认 400 行以上）。动态数组向下方溢出，行挨着行会互相阻挡，结果是 `#VALUE!`。
- 一个工作簿、一张表、多个公式，比多张表并发稳定；多表并发时 EDB 会整体挂住。
- `EDB(code, start, end, options)` 第 4 个参数不能传空串，否则 `#VALUE!`（即使传 `"unit=1"` 也一样，本机 EDB 无权限）。
- 宏观 EDB 数据改用 WindPy `w.edb(code, begin, end, "Fill=Previous")`，比 Excel EDB 公式可靠得多，G/M/S 代码都能取。
- 中债收益率曲线的 Wind 代码**不带后缀**：`S0059749`（10Y）、`S0059744`（1Y）、`S0059724`（AA+ 3 年中票）。加 `.IB` / `.WI` 反而取不到。
- 一次会话取 5 个 5000 点级别的序列约 5 分钟，主要是 Excel 端计算耗时。

## 3. 各指标数据来源

### 大类资产 / 宏观
- 中国 GDP、美国 GDP 及分项：Wind EDB（`M0039354`、`G0000002`、`G0001773`、`G0001777`、`G0001784`、`G0001791`）
- 10Y 美债：东方财富公开数据（美国财政部口径），2010 年起
- 中债收益率（1Y / 10Y / AA+ 3Y）：Wind WSD `S0059744` / `S0059749` / `S0059724`，2005 年起
- 美国净出口拉动：Wind EDB `G0001784` 官方值（2026-11-23 起替换残差估算）

### A股情绪（页面 `sentiment`）

| 指标 | 数据 | 来源 | 状态 |
|---|---|---|---|
| A股成交额 | `amt` | Wind 881001.WI | ✅ 2005 起 |
| 换手率 | `turn` | Wind 881001.WI | ✅ 2005 起 |
| 上涨家数占比 | 涨/跌家数 | — | ❌ 待补 |
| 融资买入 / 成交额 | `RZMRE` | 东财两融历史 | ✅ 2010-03 起 |
| 融资余额 / 流通市值 | `RZYEZB` | 东财两融历史 | ✅ 2010-03 起 |
| 全A PE(TTM) | `pe_ttm` | Wind 881001.WI | ✅ 2005 起 |
| 全A PB | `pb_lf` | Wind 881001.WI | ✅ 2005 起 |
| ERP = EP − 10Y 国债 | `pe_ttm` + `S0059749` | Wind | ✅ 2005 起 |

## 4. 待补数据

| 指标 | 想用的源 | 当前状态 |
|---|---|---|
| 上涨 / 下跌家数（日频历史） | Wind EDB 涨跌家数 | 待补：需确认 EDB 代码，WindPy 已可用 |
| A股总市值 | Wind `mkt_cap` | 指数字段返回空，仅 `mkt_cap_ard`（流通市值）可用 |

## 5. 检索经验

- Wind EDB 的中文正式名是「GDP环比拉动率」，不要用英文名直译去搜。
- Wind 指数字段：`mkt_cap_ard` 可用（流通市值），`mkt_cap` / `total_mv` / `mkt_cap_total` 都返回空。
- 指数没有 `up_num` / `down_num` / `rise_num` 之类字段，家数只能在 EDB 或逐日板块统计里拿。

## 6. WindPy 用法（宏观 EDB 主通道）

前提：终端「量化接口修复工具」完成 Python 接口配置（一次性）。之后 `w.start()` 返回 0 即连通。

```python
import sys
sys.path.insert(0, r"D:\Wind\Wind.NET.Client\WindNET\x64")
from WindPy import w
w.start()                       # 返回 0 即连通
r = w.edb("G0001791", "2011-03-31", "2026-09-30", "Fill=Previous")  # G=国际宏观，M=中国宏观，S=利率
# r.ErrorCode == 0 表示成功；r.Times 是期数序列，r.Data[0] 是值
```

- 季度数据更新脚本：`scripts/fetch_quarters.py`（取 G 代码对齐 `quarters.json`，只动待补字段）。
- 常见坑：`w.start()` 返回 -2 = 终端本地量化 API 服务没起（不是权限、不是 Python 版本、不是 dll），跑一次「量化接口修复工具」即可。
