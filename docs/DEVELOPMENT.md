# 开发与维护

## 目录结构

```
index.html                 页面骨架
assets/css/style.css       样式
assets/js/app.js           渲染引擎（一般不用改）
assets/js/registry.js      ★ 图表注册表：加图、改图只改这里
assets/vendor/echarts.min.js
data/market-data.js        页面读取的数据（由脚本生成，勿手改）
data/source/quarters.json  ★ 季度数据存量（GDP 及分项），只追加不重取
scripts/build_data.py      生成 market-data.js（增量拉美债）
scripts/merge_quarters.py  把新季度并入存量
```

## 页面结构

| 页面 | 路由 | 当前图表 |
|---|---|---|
| 中国宏观 | `#/cn-macro` | 图 1 中国 GDP 不变价当季同比 |
| 海外宏观 | `#/overseas` | 图 2 美国 GDP 增速与结构 |
| 大类资产 | `#/assets` | 图 3 美国 10 年期国债收益率 |

每张图都有全局唯一编号，编号显示在卡片左上角。

### 布局规则（默认两列）

页面容器 `.page` 是两列网格：**一排两张图，左一张右一张**。新增图不需要写任何布局代码，会自动按顺序填格子。

- 每组（`group`）的卡片数为偶数 → 正好两两成排
- 卡片数为奇数 → **落单的最后一张自动占满整行**（`.span-2`），避免右半留空
- 顶部总览面板 `.overview` 与分组标题 `.group-head` 始终占满整行
- 窗口宽度 ≤900px 时回退为单列（手机 / 窄屏）

这套规则由 `app.js` 的 `renderPages()` 自动判定，不要在 `registry.js` 里手写布局字段。

## 时间轴交互

- 底部滑块：拖动两端缩放、拖中间平移
- 图表内滚轮缩放、按住拖动平移
- 右上角快捷区间（5年 / 10年 / 全部 等），点击即切换

## 数据更新（增量，不重取历史）

脚本为增量模式，日常更新不会重复拉历史，也不会反复消耗 Wind 积分。

**① 日频指标（10Y 美债）—— 零积分**

```bash
python scripts/build_data.py
```

只从本地最后日期往前 10 天拉取（覆盖修订），与旧数据合并去重，通常只拉回十几个点。顺带会自动改写 `index.html` 里数据文件的版本号，确保浏览器刷新即见新数据，不会被缓存挡住。

**② 季度指标（中/美 GDP 及分项）—— 每季一次**

只有新季度公布时才需要动。通过 Wind 取**最近 4 期**（不是全历史），并入存量：

```bash
python scripts/merge_quarters.py --data '[{"period":"2026Q4","cn_gdp_yoy":4.6,"us_gdp_saar":1.8,"us_contrib_pce":1.5,"us_contrib_inv":0.2,"us_contrib_gov":0.1}]'
python scripts/build_data.py
```

脚本会自动去重（同期覆盖）、校验连续性（跳期报错）、校验各序列等长。
`us_contrib_net` 不用填，由残差自动计算。

**③ 校验**（不联网、不写文件）

```bash
python scripts/build_data.py --check
```

**④ 全量重拉**（换数据源、修历史时）

```bash
python scripts/build_data.py --full
```

顶栏右上角显示的是日频数据的最后日期；若超过 7 天未更新会变成橙色并提示"待更新"。

## 加一张新图（三步）

1. **取数**。在 `scripts/build_data.py` 里加一个序列，或在数据源取好后手工追加到 `data/market-data.js` 的 `series` 中，格式：

```js
"我的指标key": {
  "title": "指标名称", "unit": "%", "freq": "M",
  "source": "数据来源",
  "dates": ["2024-01-31", "2024-02-29"],   // 月度/日度用日期
  "labels": ["2024-01", "2024-02"],         // 季度用标签，可省略
  "values": [1.2, 1.5]
}
```

2. **注册图表**。在 `assets/js/registry.js` 的 `charts` 数组末尾追加：

```js
{
  id: 4,                       // 新编号，递增且不要重复
  page: "cn-macro",            // 放到哪个页面
  title: "中国 CPI 同比",
  subtitle: "月度 · 国家统计局",
  unit: "%",
  axisType: "time",            // 月度、日度用 time；季度用 category
  series: [
    { key: "我的指标key", name: "CPI 同比", type: "line", color: "orange", area: true }
  ],
  ranges: [{ label: "3年", periods: 36 }, { label: "全部", periods: null }],
  default: "3年",
  source: "国家统计局 / Wind"
}
```

3. 刷新页面，侧边栏该页面的图表计数会自动 +1。

可选字段：`axisTickBy: "Q1"`（季度轴按年对齐）、`statKey`（卡片右上角主数值用哪个系列）、`deltaMode: "bp"`（利率变动按 bp 显示）、`note`（底部提示）、`tooltipUnit: false`（多系列单位不统一时不显示单位）。

图表类型：`type: "line"` 或 `"bar"`；多个 `bar` 给相同 `stack` 值即堆叠。

---

## A股情绪板块（page: sentiment）

与前三个板块不同：数据不走 `market-data.js`，而是独立文件 `data/sentiment-data.js`，因为体量大（约 5000 个交易日 × 8 个序列）。

### 数据链路

```
Wind 终端 Excel 插件（WSD 公式）
  ↓ python scripts/wind_fetch.py run config.json data/source/wind_core.json
data/source/wind_core.json          # 881001.WI 的成交额/换手率/PE/PB/流通市值
data/source/bond.json               # 中债收益率 1Y/10Y/AA+3Y
  ↓ python scripts/fetch_margin.py
data/source/margin.json             # 东财两融历史
  ↓ python scripts/build_sentiment_source.py
data/source/sentiment.json          # 原料：按交易日对齐后的原始字段
  ↓ python scripts/build_sentiment.py
data/sentiment-data.js              # 成品：8 个衍生指标 + 分位 + 汇总
```

也可以绕过 Wind，直接把手工整理的底表导入：

```bash
python scripts/import_sentiment.py --file <csv/xlsx>
```

取数通道可用性、代码与字段清单见 `docs/DATA-SOURCES.md`。

### 原料字段

`data/source/sentiment.json` 的 `raw` 下支持这些字段（缺哪个，对应指标自动留空）：

| 字段 | 含义 | 单位 |
|---|---|---|
| `amount` | A股成交额 | 元 |
| `mktcap_total` / `mktcap_float` | A股总市值 / 流通市值 | 元 |
| `turnover` | 换手率（缺省时由成交额÷流通市值算） | % |
| `adv` / `dec` | 上涨家数 / 下跌家数 | 家 |
| `pe` / `pb` | 全A 市盈率 TTM / 市净率 | 倍 |
| `y10` | 10 年期国债收益率 | % |
| `margin_buy` / `margin_bal` | 融资买入额 / 融资余额 | 元 |

### 8 个指标与口径

| key | 指标 | 维度 | 算法 |
|---|---|---|---|
| `sent_amt_cap` | A股成交额 | 量 | amount ÷ 1e8（亿元） |
| `sent_turnover` | 换手率 | 量 | 直接取，或 amount ÷ mktcap_float |
| `sent_advance` | 上涨家数占比 | 价 | adv ÷ (adv + dec)　**数据待补** |
| `sent_mbuy` | 融资买入 / 成交额 | 资金 | margin_buy ÷ amount |
| `sent_mbal` | 融资余额 / 流通市值 | 资金 | 优先取 `margin_bal_float_ratio`，否则 margin_bal ÷ mktcap_float |
| `sent_pe` | 全A 市盈率 TTM | 估值 | 直接取 |
| `sent_pb` | 全A 市净率 | 估值 | 直接取 |
| `sent_erp` | EP − 10Y 国债 | 风险溢价 | 100 ÷ pe − y10 |

### 分位与情绪温度

- 每个指标输出两条数组：`values`（原值）与 `pctl`（**全历史分位**，自数据起点扩展窗口，0–100）
- 顶部总览的「情绪温度」= 8 个指标分位的算术均值
- **ERP 做方向反转**：ERP 高代表便宜、情绪低，因此汇总时用 `100 − pctl`。该反转在 `build_sentiment.py` 的 `SPECS` 里由 `invert=True` 控制

### 加一个情绪指标

1. 在 `build_sentiment.py` 的 `SPECS` 里加一行 `(key, 名称, 单位, 维度, 小数位, 是否反向)`
2. 在 `values` 字典里算出该指标序列
3. 在 `import_sentiment.py` 的 `ALIASES` 里登记底表列名（如果来自新字段）
4. 在 `registry.js` 里加一张图，给 `dataKey: "新key"` 和 `modeToggle: true`
5. 依次跑 `import_sentiment.py` → `build_sentiment.py`

### 注意

`build_sentiment.py --demo` 会用随机序列生成占位数据，并在 `meta.demo = true`；页面上会出现红色「示例数据」角标。**正式上线前必须用真实底表重建**，不能把 demo 数据推上去。

当前线上为真实数据（2005-01-04 起 5314 个交易日）。8 个指标中 7 个有真实序列，`sent_advance`（上涨家数占比）因缺日频历史源暂为空，页面上标注「数据待补」。
