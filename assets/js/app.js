/* ============================================================================
 * 渲染引擎：读取 registry.js 配置 + market-data.js 数据，生成看板
 * 一般无需改动此文件；新增指标请只修改 registry.js
 * ========================================================================== */
(function () {
  "use strict";

  var CFG = window.DASHBOARD_CONFIG;
  var DATA = (window.MARKET_DATA && window.MARKET_DATA.series) || {};

  var PALETTE = {
    blue: "#1e4b8f",
    red: "#c8362f",
    orange: "#e0913a",
    green: "#17835b",
    purple: "#6b5b95",
    teal: "#3d8ea8",
    ink: "#2b3240",
    gray: "#8a919e"
  };

  var FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif';
  var instances = new Map();   // chartId -> echarts instance
  var observers = new Map();   // chartId -> ResizeObserver
  var currentPage = null;

  /* ------------------------------ utils ------------------------------ */
  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }
  function fmt(v, d) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    return Number(v).toFixed(d === undefined ? 2 : d);
  }
  function seriesOf(key) {
    return DATA[key] || null;
  }
  function lastTwo(values) {
    var last = null, prev = null;
    for (var i = values.length - 1; i >= 0; i--) {
      var v = values[i];
      if (v === null || v === undefined) continue;
      if (last === null) { last = v; }
      else { prev = v; break; }
    }
    return { last: last, prev: prev };
  }
  function xData(chart) {
    var s = seriesOf(chart.series[0].key);
    if (!s) return [];
    return chart.axisType === "time" ? s.dates : (s.labels || s.dates);
  }

  /* --------------------------- option build --------------------------- */
  function buildOption(chart) {
    var xs = xData(chart);
    var n = xs.length;
    var multi = chart.series.length > 1;
    var showLegend = multi || chart.legend === true;

    var zoom = { start: 0, end: 100 };
    var defRange = (chart.ranges || []).filter(function (r) { return r.label === chart.default; })[0];
    if (defRange && defRange.periods && defRange.periods < n) {
      zoom.start = ((n - defRange.periods) / n) * 100;
    }

    var xAxis = chart.axisType === "time"
      ? {
          type: "time",
          boundaryGap: false,
          axisLine: { lineStyle: { color: "#e2e5ea" } },
          axisTick: { show: false },
          axisLabel: {
            color: "#949ba6", fontSize: 11, hideOverlap: true, margin: 10,
            formatter: function (val) {
              var d = new Date(val);
              return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2);
            }
          },
          splitLine: { show: false }
        }
      : {
          type: "category",
          boundaryGap: showLegend,
          data: xs,
          axisLine: { lineStyle: { color: "#e2e5ea" } },
          axisTick: { show: false },
          axisLabel: {
            color: "#949ba6", fontSize: 11, hideOverlap: true, margin: 12,
            interval: chart.axisTickBy
              ? function (i, v) { return new RegExp(chart.axisTickBy + "$").test(v); }
              : "auto"
          },
          splitLine: { show: false }
        };

    var series = chart.series.map(function (s) {
      var src = seriesOf(s.key);
      var color = PALETTE[s.color] || s.color || PALETTE.blue;
      var item = {
        name: s.name,
        type: s.type,
        yAxisIndex: s.yAxisIndex || 0,
        itemStyle: { color: color },
        emphasis: { focus: "series" },
        z: s.type === "line" ? 12 : 2
      };

      if (s.type === "bar") {
        item.stack = s.stack || null;
        item.barWidth = s.barWidth || "58%";
      }
      if (s.type === "line") {
        item.width = s.width || 2;
        item.lineStyle = { width: s.width || 2, color: color };
        item.smooth = !!s.smooth;
        item.symbol = chart.axisType === "time" ? "none" : "circle";
        item.symbolSize = 4;
        item.showSymbol = chart.axisType !== "time";
        if (chart.axisType === "time") item.sampling = "lttb";
        if (s.area) {
          item.areaStyle = {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: hexA(color, 0.22) },
              { offset: 1, color: hexA(color, 0.01) }
            ])
          };
        }
        if (s.dashed) item.lineStyle.type = "dashed";
      }

      if (!src) { item.data = []; return item; }

      if (chart.axisType === "time") {
        var d = [], v = src.values;
        for (var i = 0; i < src.dates.length; i++) {
          if (v[i] === null || v[i] === undefined) continue;
          d.push([src.dates[i], v[i]]);
        }
        item.data = d;
        if (s.type === "bar") delete item.sampling;
      } else {
        item.data = src.values;
      }
      return item;
    });

    var opt = {
      animationDuration: 480,
      animationEasing: "cubicOut",
      textStyle: { fontFamily: FONT },
      grid: {
        left: 6, right: 20,
        top: showLegend ? 44 : 22,
        bottom: 68,
        containLabel: true
      },
      legend: showLegend ? {
        top: 6, left: 0, icon: "roundRect",
        itemWidth: 9, itemHeight: 9, itemGap: 16,
        textStyle: { color: "#5f6773", fontSize: 11.5 }
      } : { show: false },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(255,255,255,.98)",
        borderColor: "#e2e5ea",
        borderWidth: 1,
        padding: [9, 12],
        textStyle: { color: "#1a1f29", fontSize: 12 },
        extraCssText: "box-shadow:0 6px 20px rgba(20,28,45,.10);border-radius:8px;",
        axisPointer: {
          type: "line",
          lineStyle: { color: "#c3cbd8", width: 1, type: "dashed" }
        },
        formatter: function (params) {
          if (!params.length) return "";
          var head = params[0].axisValueLabel || params[0].axisValue;
          var rows = params.map(function (p) {
            var v = p.value;
            if (Array.isArray(v)) v = v[1];
            var unit = chart.tooltipUnit === false
              ? ""
              : (p.seriesName && chart.seriesUnit && chart.seriesUnit[p.seriesName]) || chart.unit || "";
            return '<div style="display:flex;align-items:center;gap:14px;justify-content:space-between;margin-top:5px">' +
              '<span style="color:#5f6773">' + p.marker + p.seriesName + "</span>" +
              '<span style="font-variant-numeric:tabular-nums;font-weight:600">' + fmt(v) +
              (unit ? '<span style="color:#949ba6;font-weight:400;font-size:11px"> ' + unit + "</span>" : "") +
              "</span></div>";
          }).join("");
          return '<div style="font-size:12px;font-weight:600;color:#1a1f29">' + head + "</div>" + rows;
        }
      },
      xAxis: xAxis,
      yAxis: {
        type: "value",
        scale: true,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: "#949ba6", fontSize: 11, margin: 10,
          formatter: function (v) { return v + (chart.unit === "%" ? "%" : ""); }
        },
        splitLine: { lineStyle: { color: "#f0f2f6", type: "dashed" } }
      },
      dataZoom: [
        { type: "inside", start: zoom.start, end: zoom.end, throttle: 60 },
        {
          type: "slider",
          start: zoom.start, end: zoom.end,
          height: 22, bottom: 6,
          borderColor: "transparent",
          backgroundColor: "#f6f7fa",
          fillerColor: "rgba(30,75,143,.13)",
          handleSize: "90%",
          handleStyle: { color: "#fff", borderColor: "#aab4c4", borderWidth: 1 },
          moveHandleSize: 5,
          moveHandleStyle: { color: "#c9d1de" },
          dataBackground: {
            lineStyle: { color: "#c2cad6", width: 1 },
            areaStyle: { color: "#eceff5" }
          },
          selectedDataBackground: {
            lineStyle: { color: "#6f8ab5", width: 1 },
            areaStyle: { color: "rgba(30,75,143,.14)" }
          },
          textStyle: { color: "#a4abb6", fontSize: 10 },
          brushSelect: false
        }
      ],
      series: series
    };
    return opt;
  }

  function hexA(hex, a) {
    var h = hex.replace("#", "");
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    return "rgba(" + r + "," + g + "," + b + "," + a + ")";
  }

  /* ---------------------------- card render ---------------------------- */
  function buildCard(chart) {
    var card = el("section", "card");
    card.dataset.chartId = chart.id;

    var head = el("div", "card-head");
    head.appendChild(el("div", "card-id", chart.id));
    var tw = el("div", "card-title-wrap");
    tw.appendChild(el("h2", "card-title", chart.title));
    tw.appendChild(el("div", "card-sub", chart.subtitle || ""));
    head.appendChild(tw);

    // 主数值
    var statKey = chart.statKey || chart.series[0].key;
    var statSrc = seriesOf(statKey);
    var stat = el("div", "card-stat");
    if (statSrc) {
      var lt = lastTwo(statSrc.values);
      var va = el("div", "stat-value num", fmt(lt.last) +
        '<span class="stat-unit">' + (chart.unit || "") + "</span>");
      stat.appendChild(va);
      if (lt.prev !== null) {
        var diff = lt.last - lt.prev;
        var txt;
        if (chart.deltaMode === "bp") {
          txt = "较前值 " + (diff >= 0 ? "+" : "") + (diff * 100).toFixed(1) + " bp";
        } else {
          txt = "较上期 " + (diff >= 0 ? "+" : "") + diff.toFixed(2);
        }
        var dcls = "stat-delta num " + (diff >= 0 ? "up" : "down");
        stat.appendChild(el("div", dcls, txt));
      }
    }
    head.appendChild(stat);
    card.appendChild(head);

    // 区间按钮
    if (chart.ranges && chart.ranges.length) {
      var bar = el("div", "ranges");
      chart.ranges.forEach(function (r) {
        var btn = el("button", "range-btn" + (r.label === chart.default ? " active" : ""), r.label);
        btn.dataset.periods = r.periods === null ? "" : r.periods;
        btn.addEventListener("click", function () {
          bar.querySelectorAll(".range-btn").forEach(function (b) { b.classList.remove("active"); });
          btn.classList.add("active");
          applyRange(chart, r.periods);
        });
        bar.appendChild(btn);
      });
      // 放在标题行右侧
      var head2 = card.querySelector(".card-head");
      head2.appendChild(bar);
    }

    var chartEl = el("div", "chart");
    chartEl.id = "chart-" + chart.id;
    card.appendChild(chartEl);

    var foot = el("div", "card-foot");
    var src = seriesOf(chart.series[0].key);
    var lastLabel = src ? (src.labels ? src.labels[src.labels.length - 1] : src.dates[src.dates.length - 1]) : "";
    foot.appendChild(el("span", "src", "数据来源：" + (chart.source || "—")));
    if (chart.note) foot.appendChild(el("span", "note", chart.note));
    foot.appendChild(el("span", "latest num", "最新 " + lastLabel));
    card.appendChild(foot);

    return card;
  }

  function applyRange(chart, periods) {
    var inst = instances.get(chart.id);
    if (!inst) return;
    var n = xData(chart).length;
    var start = (!periods || periods >= n) ? 0 : ((n - periods) / n) * 100;
    inst.dispatchAction({ type: "dataZoom", start: start, end: 100 });
  }

  /* ------------------------------- pages ------------------------------- */
  function watchSize(card, inst, id) {
    if (!window.ResizeObserver) return;
    var target = card.querySelector(".chart");
    var raf = null;
    var ro = new ResizeObserver(function () {
      if (target.clientWidth <= 0) return;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(function () { inst.resize(); });
    });
    ro.observe(target);
    observers.set(id, ro);
  }

  function renderPages() {
    var content = document.getElementById("content");
    var nav = document.getElementById("nav");

    CFG.pages.forEach(function (page, idx) {
      var sec = el("div", "page");
      sec.id = "page-" + page.id;

      CFG.charts.filter(function (c) { return c.page === page.id; })
        .sort(function (a, b) { return a.id - b.id; })
        .forEach(function (c) { sec.appendChild(buildCard(c)); });

      content.appendChild(sec);

      var btn = el("button", "nav-item");
      btn.dataset.page = page.id;
      btn.innerHTML = '<span>' + page.name + "</span>" +
        '<span class="nav-count">' + sec.children.length + "</span>";
      btn.addEventListener("click", function () { location.hash = "#/" + page.id; });
      nav.appendChild(btn);
    });
  }

  function activate(pageId) {
    if (!CFG.pages.some(function (p) { return p.id === pageId; })) {
      pageId = CFG.pages[0].id;
    }
    currentPage = pageId;

    document.querySelectorAll(".page").forEach(function (p) {
      p.classList.toggle("active", p.id === "page-" + pageId);
    });
    document.querySelectorAll(".nav-item").forEach(function (b) {
      b.classList.toggle("active", b.dataset.page === pageId);
    });

    var page = CFG.pages.filter(function (p) { return p.id === pageId; })[0];
    document.getElementById("pageTitle").textContent = page.name;
    document.getElementById("pageDesc").textContent = page.desc || "";

    requestAnimationFrame(function () {
      CFG.charts.filter(function (c) { return c.page === pageId; }).forEach(function (c) {
        var card = document.querySelector('.card[data-chart-id="' + c.id + '"]');
        if (!card) return;
        var inst = instances.get(c.id);
        if (!inst) {
          inst = echarts.init(card.querySelector(".chart"), null, { renderer: "canvas" });
          inst.setOption(buildOption(c));
          instances.set(c.id, inst);
          watchSize(card, inst, c.id);
        } else {
          inst.resize();
        }
      });
    });
  }

  /* ------------------------------- boot ------------------------------- */
  function boot() {
    if (!window.echarts || !window.MARKET_DATA) {
      document.getElementById("content").innerHTML =
        '<div style="padding:40px;color:#c8362f">脚本或数据加载失败，请确认 assets/vendor/echarts.min.js 与 data/market-data.js 是否存在。</div>';
      return;
    }

    document.title = CFG.title;

    // 顶栏：以日频序列的最后日期作为"数据新鲜度"基准
    var daily = window.MARKET_DATA.series && window.MARKET_DATA.series.us10y_yield;
    var lastDate = daily && daily.dates.length
      ? daily.dates[daily.dates.length - 1]
      : (window.MARKET_DATA.meta && window.MARKET_DATA.meta.generatedAt) || "";
    var updEl = document.getElementById("updatedAt");
    if (lastDate) {
      var staleDays = (Date.now() - new Date(lastDate + "T00:00:00").getTime()) / 86400000;
      updEl.textContent = "数据至 " + lastDate + (staleDays > 7 ? " · 待更新" : "");
      if (staleDays > 7) {
        var upd = updEl.parentElement;
        if (upd) upd.classList.add("stale");
      }
    }

    renderPages();

    window.addEventListener("hashchange", function () {
      activate(location.hash.replace("#/", "") || CFG.pages[0].id);
    });
    activate(location.hash.replace("#/", "") || CFG.pages[0].id);
  }

  boot();
})();
