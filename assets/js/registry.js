/* ============================================================================
 * 图表注册表 —— 全站唯一需要修改的配置文件
 * ----------------------------------------------------------------------------
 * 新增一张图：在 charts 数组里追加一个对象，给一个新的 id 即可，页面会自动渲染。
 *
 * 字段说明：
 *   id         全局唯一编号（正整数，递增）。以后说"改图 7"即指这里的 id。
 *   page       所属页面 id（见 pages）
 *   title      图标题
 *   subtitle   副标题（频率 · 口径）
 *   unit       单位，用于数值展示与 tooltip
 *   axisType   'category' 季度/离散期数  |  'time' 日度、月度
 *   series[]   数据系列，key 指向 data/market-data.js 里 series 的键
 *              { key, name, type:'line'|'bar', color, stack?, area?, dashed?, width? }
 *   ranges     时间快捷区间 [{ label, periods }]，periods 为显示最近若干期，null=全部
 *   default    默认区间 label
 *   source     数据来源（显示在卡片底部）
 * ========================================================================== */
window.DASHBOARD_CONFIG = {
  title: "宏观与市场指标看板",

  pages: [
    { id: "cn-macro", name: "中国宏观", desc: "经济增长、价格与政策脉络" },
    { id: "overseas", name: "海外宏观", desc: "美国及主要经济体增长与结构" },
    { id: "assets",   name: "大类资产", desc: "利率、汇率、权益与商品价格" }
  ],

  charts: [
    /* ---------------------------------------------------------------- 图 1 */
    {
      id: 1,
      page: "cn-macro",
      title: "中国 GDP 不变价当季同比",
      subtitle: "季度 · 国家统计局口径",
      unit: "%",
      axisType: "category",
      axisTickBy: "Q1",
      series: [
        { key: "cn_gdp_yoy", name: "GDP 当季同比", type: "line", color: "red", area: true, width: 2.2 }
      ],
      ranges: [
        { label: "5年", periods: 20 },
        { label: "10年", periods: 40 },
        { label: "全部", periods: null }
      ],
      default: "全部",
      source: "国家统计局 / Wind EDB（M0039354）"
    },

    /* ---------------------------------------------------------------- 图 2 */
    {
      id: 2,
      page: "overseas",
      title: "美国 GDP 增速与结构",
      subtitle: "季度 · 实际 GDP 季调环比折年率及分项拉动",
      unit: "%",
      axisType: "category",
      statKey: "us_gdp_saar",
      tooltipUnit: false,
      series: [
        { key: "us_contrib_pce", name: "个人消费支出", type: "bar", color: "red",    stack: "y" },
        { key: "us_contrib_inv", name: "私人投资",     type: "bar", color: "blue",   stack: "y" },
        { key: "us_contrib_gov", name: "政府支出",     type: "bar", color: "purple", stack: "y" },
        { key: "us_contrib_net", name: "净出口（估算）", type: "bar", color: "teal",   stack: "y" },
        { key: "us_gdp_saar",    name: "实际 GDP",     type: "line", color: "ink",   width: 2 }
      ],
      ranges: [
        { label: "5年", periods: 20 },
        { label: "10年", periods: 40 },
        { label: "全部", periods: null }
      ],
      default: "5年",
      note: "净出口为残差估算 · 2026Q3 政府项缺",
      source: "BEA / Wind EDB（G0000002、G0001773、G0001777、G1140985）；净出口待补 G0001784"
    },

    /* ---------------------------------------------------------------- 图 3 */
    {
      id: 3,
      page: "assets",
      title: "美国 10 年期国债收益率",
      subtitle: "日度 · 美国财政部国债收益率曲线",
      unit: "%",
      axisType: "time",
      deltaMode: "bp",
      series: [
        { key: "us10y_yield", name: "10Y 美债收益率", type: "line", color: "blue", area: true, width: 1.6 }
      ],
      ranges: [
        { label: "6个月", periods: 125 },
        { label: "1年",   periods: 250 },
        { label: "3年",   periods: 750 },
        { label: "全部",  periods: null }
      ],
      default: "3年",
      source: "美国财政部 / 东方财富（Wind 积分不足时的替代源）"
    }
  ]
};
