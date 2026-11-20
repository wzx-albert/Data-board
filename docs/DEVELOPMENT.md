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
