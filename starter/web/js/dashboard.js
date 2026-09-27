/* 标签 1：经营看板。图表是手写 SVG，没有引入任何图表库。 */
'use strict';

var Dashboard = (function () {

  var SVG_NS = 'http://www.w3.org/2000/svg';

  /* 清洗剔除原因：键名来自后端 cleaning_report.removed，界面上一律显示中文。
     note_unparseable_amount 是「备注」而不是剔除类别，单独放在最后。 */
  var REMOVAL_LABELS = [
    ['1_unparseable_date', '日期无法解析'],
    ['2_empty_amount', '金额为空'],
    ['3_qty_le_zero', '数量 ≤ 0'],
    ['4_store_not_in_stores', '门店外键不存在'],
    ['5_product_not_in_products', '商品外键不存在'],
    ['6_duplicate_row', '完全重复行'],
    ['note_unparseable_amount', '金额无法解析（备注）']
  ];

  var state = {
    defaults: { start: '', end: '' },
    days: [],
    hover: -1,
    health: null
  };

  /* ------------------------------ 绘图 ------------------------------ */

  function svgNode(tag, attrs, text) {
    var node = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    return node;
  }

  /** 把最大值向上取到一个「好看」的刻度值。 */
  function niceMax(value) {
    var max = Number(value) || 0;
    if (!(max > 0)) { return 100; }
    var exponent = Math.floor(Math.log10(max));
    var base = Math.pow(10, exponent);
    var normalized = max / base;
    var steps = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
    for (var i = 0; i < steps.length; i += 1) {
      if (normalized <= steps[i] + 1e-9) { return steps[i] * base; }
    }
    return 10 * base;
  }

  function drawChart() {
    var svg = U.$('trend-svg');
    if (!svg) { return; }
    var wrap = U.$('trend-wrap');
    var width = Math.max(320, Math.floor(wrap.clientWidth || 720));
    var height = 320;
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    while (svg.firstChild) { svg.removeChild(svg.firstChild); }

    var days = state.days;
    if (!days.length) {
      svg.appendChild(svgNode('text', {
        x: width / 2, y: height / 2, 'text-anchor': 'middle',
        fill: '#94a3b8', 'font-size': '13'
      }, '当前筛选区间内没有数据'));
      return;
    }

    var pad = { top: 18, right: 22, bottom: 34, left: 64 };
    var plotW = Math.max(10, width - pad.left - pad.right);
    var plotH = Math.max(10, height - pad.top - pad.bottom);
    var scaleMax = niceMax(Math.max.apply(null, days.map(function (day) {
      return Number(day.net_revenue) || 0;
    })));

    function px(index) {
      return days.length === 1
        ? pad.left + plotW / 2
        : pad.left + (index / (days.length - 1)) * plotW;
    }
    function py(value) {
      var ratio = Math.max(0, Math.min(1, (Number(value) || 0) / scaleMax));
      return pad.top + plotH - ratio * plotH;
    }

    // 网格线与 Y 轴刻度。
    // 只画 4 条极浅的横线：123 天的折线本身已经很密，网格线一多整张图就糊了。
    // 基线略深一点，用来交代「0 在哪」。
    var ticks = 4;
    for (var t = 0; t <= ticks; t += 1) {
      var value = scaleMax * t / ticks;
      var y = py(value);
      svg.appendChild(svgNode('line', {
        x1: pad.left, x2: pad.left + plotW, y1: y, y2: y,
        stroke: t === 0 ? '#dbe2ec' : '#f2f5fa', 'stroke-width': 1
      }));
      svg.appendChild(svgNode('text', {
        x: pad.left - 8, y: y + 4, 'text-anchor': 'end',
        fill: '#94a3b8', 'font-size': '11'
      }, U.compact(value)));
    }

    // X 轴刻度：最多 8 个，避免日期挤在一起
    var labelStep = Math.max(1, Math.ceil(days.length / 8));
    for (var i = 0; i < days.length; i += labelStep) {
      svg.appendChild(svgNode('text', {
        x: px(i), y: pad.top + plotH + 18, 'text-anchor': 'middle',
        fill: '#94a3b8', 'font-size': '11'
      }, U.shortDate(days[i].date)));
    }
    svg.appendChild(svgNode('text', {
      x: pad.left + plotW, y: pad.top + plotH + 18, 'text-anchor': 'end',
      fill: '#94a3b8', 'font-size': '11'
    }, days.length + ' 天'));

    // 折线 + 面积
    var points = days.map(function (day, index) {
      return [px(index), py(day.net_revenue)];
    });
    var line = points.map(function (point, index) {
      return (index === 0 ? 'M' : 'L') + point[0].toFixed(2) + ' ' + point[1].toFixed(2);
    }).join(' ');
    if (points.length > 1) {
      var area = line
        + ' L' + points[points.length - 1][0].toFixed(2) + ' ' + (pad.top + plotH).toFixed(2)
        + ' L' + points[0][0].toFixed(2) + ' ' + (pad.top + plotH).toFixed(2) + ' Z';
      svg.appendChild(svgNode('path', { d: area, fill: 'rgba(59, 91, 219, .07)', stroke: 'none' }));
    }
    svg.appendChild(svgNode('path', {
      d: line, fill: 'none', stroke: '#3b5bdb', 'stroke-width': 2,
      'stroke-linejoin': 'round', 'stroke-linecap': 'round'
    }));

    // 数据点（点少的时候画出来更清楚）
    if (days.length <= 62) {
      points.forEach(function (point) {
        svg.appendChild(svgNode('circle', {
          cx: point[0], cy: point[1], r: 2.6, fill: '#fff',
          stroke: '#3b5bdb', 'stroke-width': 1.6
        }));
      });
    }

    // 悬停辅助元素
    var guide = svgNode('line', {
      x1: 0, x2: 0, y1: pad.top, y2: pad.top + plotH,
      stroke: '#3b5bdb', 'stroke-width': 1, 'stroke-dasharray': '4 3', opacity: 0
    });
    var marker = svgNode('circle', {
      cx: 0, cy: 0, r: 4.5, fill: '#3b5bdb', stroke: '#fff', 'stroke-width': 2, opacity: 0
    });
    svg.appendChild(guide);
    svg.appendChild(marker);

    var overlay = svgNode('rect', {
      x: pad.left, y: pad.top, width: plotW, height: plotH,
      fill: 'transparent', style: 'cursor: crosshair'
    });
    svg.appendChild(overlay);

    var tip = U.$('trend-tip');

    function showTip(index) {
      if (index < 0 || index >= days.length) { return; }
      var day = days[index];
      var x = px(index);
      var y = py(day.net_revenue);
      guide.setAttribute('x1', x);
      guide.setAttribute('x2', x);
      guide.setAttribute('opacity', 1);
      marker.setAttribute('cx', x);
      marker.setAttribute('cy', y);
      marker.setAttribute('opacity', 1);

      var html = '<div class="tt-date">' + U.escapeHtml(day.date) + '</div>'
        + '<div class="tt-row"><span>净营业额</span><span>' + U.escapeHtml(U.yuan(day.net_revenue)) + '</span></div>'
        + '<div class="tt-row"><span>订单数</span><span>' + U.escapeHtml(U.int(day.orders)) + '</span></div>'
        + '<div class="tt-row"><span>客单价</span><span>' + U.escapeHtml(U.yuan(day.aov)) + '</span></div>';
      tip.innerHTML = html;
      tip.hidden = false;

      var boxWidth = wrap.clientWidth || width;
      var left = x + 14;
      if (left + tip.offsetWidth > boxWidth - 4) { left = x - tip.offsetWidth - 14; }
      if (left < 0) { left = 4; }
      var top = Math.max(0, Math.min(y - tip.offsetHeight / 2, height - tip.offsetHeight - 4));
      tip.style.left = left + 'px';
      tip.style.top = top + 'px';
    }

    function hideTip() {
      guide.setAttribute('opacity', 0);
      marker.setAttribute('opacity', 0);
      tip.hidden = true;
    }

    overlay.addEventListener('mousemove', function (event) {
      var rect = svg.getBoundingClientRect();
      var scale = rect.width ? (width / rect.width) : 1;
      var localX = (event.clientX - rect.left) * scale;
      var ratio = days.length === 1 ? 0 : (localX - pad.left) / plotW;
      var index = Math.round(ratio * (days.length - 1));
      index = Math.max(0, Math.min(days.length - 1, index));
      showTip(index);
    });
    overlay.addEventListener('mouseleave', hideTip);
  }

  /* ------------------------------ 渲染 ------------------------------ */

  function renderCards(summary) {
    var host = U.clear(U.$('metric-cards'));
    var net = Number(summary.net_revenue) || 0;
    var refund = Number(summary.refund_amount) || 0;
    var refundShare = net > 0 ? (refund / net * 100) : null;
    var items = [
      { key: '净营业额', value: U.yuan(summary.net_revenue), sub: '含退款冲减' },
      {
        key: '退款金额', value: U.yuan(summary.refund_amount),
        sub: U.isNum(refundShare) ? ('占净营业额 ' + refundShare.toFixed(2) + '%') : ''
      },
      { key: '有效订单数', value: U.int(summary.orders), sub: '销售行去重订单号' },
      {
        key: '客单价',
        value: U.isNum(summary.aov) ? ('¥' + U.money(summary.aov)) : '—',
        sub: U.isNum(summary.aov) ? '净营业额 ÷ 订单数' : '没有订单，无法计算'
      },
      { key: '销量', value: U.int(summary.qty), sub: '销售为正、退款为负' }
    ];
    items.forEach(function (item) {
      var card = U.el('div', 'metric');
      card.appendChild(U.el('div', 'k', item.key));
      card.appendChild(U.el('div', 'v', item.value));
      card.appendChild(U.el('div', 's', item.sub || ''));
      host.appendChild(card);
    });
  }

  function renderTop(payload) {
    var tbody = U.clear(U.$('top-table').querySelector('tbody'));
    var products = (payload && payload.products) || [];
    U.$('top-note').textContent = products.length
      ? ('共 ' + products.length + ' 个商品 · 按净营业额降序')
      : '';
    if (!products.length) {
      var row = U.el('tr');
      var cell = U.el('td', 'muted', '当前筛选条件下没有商品数据');
      cell.colSpan = 6;
      row.appendChild(cell);
      tbody.appendChild(row);
      return;
    }
    products.forEach(function (item, index) {
      var tr = U.el('tr');
      tr.appendChild(U.el('td', null, index + 1));

      var nameCell = U.el('td');
      nameCell.appendChild(U.el('div', null, item.product_name || '（维表里没有这个商品）'));
      nameCell.appendChild(U.el('div', 'sub', item.product_id || ''));
      tr.appendChild(nameCell);

      tr.appendChild(U.el('td', null, item.product_category || '—'));

      var rev = U.el('td', 'num', U.yuan(item.net_revenue));
      tr.appendChild(rev);
      tr.appendChild(U.el('td', 'num', U.int(item.orders)));
      tr.appendChild(U.el('td', 'num', U.int(item.qty)));
      tbody.appendChild(tr);
    });
  }

  function renderQuality(payload) {
    var host = U.clear(U.$('dq-body'));
    var report = (payload && payload.cleaning_report) || {};
    var removed = report.removed || {};
    var period = (payload && payload.data_period) || {};
    var warnings = (payload && payload.kb_warnings) || [];

    var kept = Number(report.kept_rows) || 0;
    var raw = Number(report.raw_rows) || 0;
    var keptRate = raw > 0 ? (kept / raw * 100).toFixed(2) + '%' : '—';
    U.$('dq-note').textContent = (period.start && period.end)
      ? ('数据区间 ' + period.start + ' ~ ' + period.end + ' · 保留率 ' + keptRate)
      : ('保留率 ' + keptRate);

    var kv = U.el('div', 'kv');
    kv.appendChild(U.kv('清洗前总行数', U.int(report.raw_rows)));
    kv.appendChild(U.kv('保留行数', U.int(report.kept_rows)));
    kv.appendChild(U.kv('销售行', U.int(report.kept_sales_rows)));
    kv.appendChild(U.kv('退款行', U.int(report.kept_refund_rows)));
    var health = state.health || {};
    if (health.today) { kv.appendChild(U.kv('系统的今天', health.today)); }
    if (health.valid_sales_rows !== undefined) {
      kv.appendChild(U.kv('有效销售行（索引口径）', U.int(health.valid_sales_rows)));
    }
    host.appendChild(kv);

    host.appendChild(U.el('div', 'sub', '剔除原因（占比按清洗前总行数计算）'));

    var max = 0;
    REMOVAL_LABELS.forEach(function (pair) {
      var value = Number(removed[pair[0]]) || 0;
      if (value > max) { max = value; }
    });
    REMOVAL_LABELS.forEach(function (pair) {
      var value = Number(removed[pair[0]]) || 0;
      var share = raw > 0 ? (value / raw * 100) : 0;
      var text = U.int(value) + ' 行 · ' + share.toFixed(2) + '%';
      host.appendChild(U.bar(pair[1], value, max, text));
    });

    var totalRemoved = 0;
    Object.keys(removed).forEach(function (key) {
      if (key === 'note_unparseable_amount') { return; }
      totalRemoved += Number(removed[key]) || 0;
    });
    host.appendChild(U.el('div', 'sub',
      '六类合计剔除 ' + U.int(totalRemoved) + ' 行；剔除顺序按 KB-001 §3，前者剔除后不再参与后续判断。'));

    if (warnings.length) {
      host.appendChild(U.el('div', 'sub', '知识库告警（' + warnings.length + ' 条）'));
      var list = U.el('ul', 'warn-list');
      warnings.forEach(function (text) { list.appendChild(U.el('li', null, text)); });
      host.appendChild(list);
    } else {
      host.appendChild(U.el('div', 'sub', '知识库告警：无'));
    }
  }

  /* ------------------------------ 数据加载 ------------------------------ */

  function currentFilters() {
    return {
      start: U.$('f-start').value,
      end: U.$('f-end').value,
      store_id: U.$('f-store').value,
      product_id: U.$('f-product').value
    };
  }

  function setNote(text) {
    U.$('range-note').textContent = text || '';
  }

  function refresh(showToast) {
    var filters = currentFilters();
    if (!filters.start || !filters.end) {
      U.toast('请先选择开始与结束日期', true);
      return Promise.resolve();
    }
    if (filters.start > filters.end) {
      U.toast('开始日期不能晚于结束日期', true);
      return Promise.resolve();
    }
    var button = U.$('btn-query');
    button.disabled = true;
    setNote('查询中…');

    var summaryUrl = '/api/metrics/summary' + U.query({
      start: filters.start, end: filters.end,
      store_id: filters.store_id, product_id: filters.product_id
    });
    var dailyUrl = '/api/metrics/daily' + U.query({
      start: filters.start, end: filters.end,
      store_id: filters.store_id, product_id: filters.product_id
    });
    var topUrl = '/api/metrics/top_products' + U.query({
      start: filters.start, end: filters.end,
      store_id: filters.store_id, limit: 10
    });

    return Promise.all([
      U.api(summaryUrl),
      U.api(dailyUrl),
      U.api(topUrl),
      U.api('/api/data_quality')
    ]).then(function (results) {
      var summary = results[0];
      state.days = (results[1] && results[1].days) || [];
      renderCards(summary || {});
      state.hover = -1;
      drawChart();
      U.$('trend-note').textContent = state.days.length
        ? ('按天 · 共 ' + state.days.length + ' 天（没有营业额的日期按 0 画出）')
        : '';
      renderTop(results[2]);
      renderQuality(results[3]);
      var zeroDays = state.days.filter(function (day) { return !(Number(day.net_revenue) > 0); }).length;
      setNote('区间 ' + filters.start + ' ~ ' + filters.end
        + ' · ' + state.days.length + ' 天，其中 ' + zeroDays + ' 天净营业额为 0');
      if (showToast) { U.toast('已刷新'); }
    }).catch(function (error) {
      setNote('查询失败：' + error.message);
      U.toast('查询失败：' + error.message, true);
    }).then(function () {
      button.disabled = false;
    });
  }

  /**
   * 填下拉框：第一个选项固定是「全部」（值空串，接口收到空值就表示不过滤），
   * 后面再接接口给的真实数据。不依赖 HTML 里预置的 option。
   */
  function fillSelect(node, items, valueKey, allLabel, labelBuilder) {
    while (node.firstChild) { node.removeChild(node.firstChild); }
    var all = U.el('option', null, allLabel);
    all.value = '';
    node.appendChild(all);
    items.forEach(function (item) {
      var option = U.el('option', null, labelBuilder(item));
      option.value = item[valueKey];
      node.appendChild(option);
    });
    node.value = '';
  }

  function loadFilters() {
    return Promise.all([U.api('/api/stores'), U.api('/api/products')]).then(function (results) {
      fillSelect(U.$('f-store'), (results[0] && results[0].stores) || [], 'store_id', '全部门店',
        function (store) {
          var extra = [store.store_name, store.district].filter(Boolean).join(' · ');
          return store.store_id + (extra ? (' · ' + extra) : '');
        });
      fillSelect(U.$('f-product'), (results[1] && results[1].products) || [], 'product_id', '全部商品',
        function (product) {
          var extra = [product.product_name, product.product_category].filter(Boolean).join(' · ');
          return product.product_id + (extra ? (' · ' + extra) : '');
        });
      // 选项齐了再解禁，避免用户在列表还没填好时选中一个不存在的门店。
      U.$('f-store').disabled = false;
      U.$('f-product').disabled = false;
    }).catch(function (error) {
      U.toast('门店/商品列表加载失败：' + error.message, true);
    });
  }

  function init(health) {
    state.health = health || {};
    var period = state.health.data_period || {};
    state.defaults.start = period.start || '';
    state.defaults.end = period.end || '';
    U.$('f-start').value = state.defaults.start;
    U.$('f-end').value = state.defaults.end;

    U.$('btn-query').addEventListener('click', function () { refresh(true); });
    U.$('btn-reset').addEventListener('click', function () {
      U.$('f-start').value = state.defaults.start;
      U.$('f-end').value = state.defaults.end;
      refresh(true);
    });
    ['f-store', 'f-product'].forEach(function (id) {
      U.$(id).addEventListener('change', function () { refresh(false); });
    });
    U.$('f-end').addEventListener('change', function () { refresh(false); });

    var wrap = U.$('trend-wrap');
    if (window.ResizeObserver) {
      var ro = new ResizeObserver(function () { drawChart(); });
      ro.observe(wrap);
    } else {
      window.addEventListener('resize', drawChart);
    }

    return loadFilters().then(function () { return refresh(false); });
  }

  return {
    init: init,
    refresh: refresh,
    drawChart: drawChart,
    // 离线校验用：直接喂真实接口返回，确认渲染不炸（浏览器里也用不到）。
    __probe: {
      renderCards: renderCards, renderTop: renderTop, renderQuality: renderQuality,
      drawChart: drawChart,
      setHealth: function (health) { state.health = health; },
      setDays: function (days) { state.days = days; },
      getDays: function () { return state.days; }
    }
  };
})();

/* 浏览器里靠上面的全局变量；Node 下（语法/渲染离线校验）走模块导出。 */
if (typeof module !== 'undefined' && module.exports) { module.exports = Dashboard; }
