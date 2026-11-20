# 宏观与市场指标看板

中国与海外宏观、大类资产的交互式图表看板。纯静态页面，ECharts 已本地化，无需服务器、无需联网。

**线上地址**：https://wzx-albert.github.io/Data-board/

## 图表

| 编号 | 页面 | 内容 |
|---|---|---|
| 图 1 | 中国宏观 | 中国 GDP 不变价当季同比 |
| 图 2 | 海外宏观 | 美国 GDP 增速与结构 |
| 图 3 | 大类资产 | 美国 10 年期国债收益率 |

图表支持底部滑块缩放平移、滚轮缩放、右上角快捷区间切换。

## 本地查看

双击 `index.html` 即可打开。

## 数据来源

中国 GDP、美国 GDP 及分项取自 Wind EDB；10Y 美债因积分限制改用东方财富公开数据（美国财政部口径）。明细见 [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md)。

## 开发与维护

目录结构、数据更新流程、新增图表模板见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。
