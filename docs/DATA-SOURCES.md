# 数据来源与取数通道

## 1. 三条取数通道（2026-11-23 实测）

| 通道 | 状态 | 可取内容 | 备注 |
|---|---|---|---|
| Wind 终端 Excel 插件（WSD） | ✅ 可用 | 行情、估值、市值、成交额、换手率、中债收益率 | `scripts/wind_fetch.py`，需 Wind 终端登录并开着 |
| Wind Python 接口（WindPy） | ❌ 不可用 | — | `w.start()` 返回 -2，终端未开 Python API 权限 |
| Wind Excel 插件（EDB） | ❌ 不可用 | — | 单元格返回 `#VALUE!`，账号无宏观数据库权限 |

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
- 中债收益率曲线的 Wind 代码**不带后缀**：`S0059749`（10Y）、`S0059744`（1Y）、`S0059724`（AA+ 3 年中票）。加 `.IB` / `.WI` 反而取不到。
- 一次会话取 5 个 5000 点级别的序列约 5 分钟，主要是 Excel 端计算耗时。

## 3. 各指标数据来源

### 大类资产 / 宏观
- 中国 GDP、美国 GDP 及分项：Wind EDB（`M0039354`、`G0000002`、`G0001773`、`G0001777`、`G1140985`）
- 10Y 美债：东方财富公开数据（美国财政部口径），2010 年起
- 中债收益率（1Y / 10Y / AA+ 3Y）：Wind WSD `S0059744` / `S0059749` / `S0059724`，2005 年起
- 美国净出口拉动：BEA 分项残差估算（官方口径待补）

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
| 上涨 / 下跌家数（日频历史） | Wind EDB 涨跌家数 | EDB 无权限；WSD 指数无此字段 |
| A股总市值 | Wind `mkt_cap` | 指数字段返回空，仅 `mkt_cap_ard`（流通市值）可用 |
| 美国:GDP环比拉动率:净出口 | `G0001784` | 残差估算 |
| 美国:GDP环比拉动率:政府支出 | `G0001791` | 现用 `G1140985`，缺 2026Q3 |

## 5. 检索经验

- Wind EDB 的中文正式名是「GDP环比拉动率」，不要用英文名直译去搜。
- Wind 指数字段：`mkt_cap_ard` 可用（流通市值），`mkt_cap` / `total_mv` / `mkt_cap_total` 都返回空。
- 指数没有 `up_num` / `down_num` / `rise_num` 之类字段，家数只能在 EDB 或逐日板块统计里拿。
