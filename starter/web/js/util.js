/* 公共工具：DOM、HTTP、格式化。没有外部依赖，全站共用。 */
'use strict';

var U = (function () {

  /* ---------------- DOM ---------------- */

  function $(id) { return document.getElementById(id); }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    return node;
  }

  function clear(node) {
    if (node) { node.innerHTML = ''; }
    return node;
  }

  /* ---------------- HTTP ---------------- */

  /**
   * 统一的 JSON 请求：非 2xx 抛出一个带 status / payload 的 Error，
   * 调用方（比如 trace 的 404）可以按 status 分别处理。
   */
  function api(path, options) {
    var opts = options || {};
    var init = { method: opts.method || 'GET', headers: {} };
    if (opts.body !== undefined) {
      init.headers['Content-Type'] = 'application/json; charset=utf-8';
      init.body = JSON.stringify(opts.body);
    }
    return fetch(path, init).then(function (response) {
      return response.text().then(function (text) {
        var payload = null;
        if (text) {
          try { payload = JSON.parse(text); } catch (err) { payload = { raw: text }; }
        }
        if (!response.ok) {
          var message = (payload && (payload.error || payload.detail)) || ('HTTP ' + response.status);
          var error = new Error(typeof message === 'string' ? message : JSON.stringify(message));
          error.status = response.status;
          error.payload = payload;
          throw error;
        }
        return payload;
      });
    });
  }

  /** 把 "?a=1&b=2" 拼成查询串，空值一律丢掉。 */
  function query(params) {
    var parts = [];
    Object.keys(params).forEach(function (key) {
      var value = params[key];
      if (value === undefined || value === null || value === '') { return; }
      parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(value));
    });
    return parts.length ? ('?' + parts.join('&')) : '';
  }

  /* ---------------- 格式化 ---------------- */

  function escapeHtml(text) {
    return String(text === undefined || text === null ? '' : text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function isNum(value) {
    return typeof value === 'number' && isFinite(value);
  }

  /** 千分位整数。 */
  function int(value) {
    if (!isNum(value)) { return '—'; }
    return Math.round(value).toLocaleString('zh-CN');
  }

  /** 金额，两位小数。 */
  function money(value) {
    if (!isNum(value)) { return '—'; }
    return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  /** 金额（带 ¥）。 */
  function yuan(value) {
    if (!isNum(value)) { return '—'; }
    return '¥' + money(value);
  }

  /** 可能为 null 的数值：null/undefined 显示「—」，这是契约里 aov 的合法取值。 */
  function num(value, digits) {
    if (!isNum(value)) { return '—'; }
    return value.toLocaleString('zh-CN', {
      minimumFractionDigits: digits || 0,
      maximumFractionDigits: digits || 0
    });
  }

  function ms(value) {
    if (!isNum(value)) { return '—'; }
    return value >= 1000 ? (value / 1000).toFixed(2) + ' s' : value.toFixed(1) + ' ms';
  }

  /** 紧凑金额，给图表刻度用：12345 -> 1.2万。 */
  function compact(value) {
    if (!isNum(value)) { return '—'; }
    var abs = Math.abs(value);
    if (abs >= 100000000) { return (value / 100000000).toFixed(1) + '亿'; }
    if (abs >= 10000) { return (value / 10000).toFixed(abs >= 100000 ? 0 : 1) + '万'; }
    if (abs >= 1000) { return (value / 1000).toFixed(1) + 'k'; }
    return String(Math.round(value));
  }

  /** 日期显示：2026-07-01 -> 07-01。 */
  function shortDate(iso) {
    var text = String(iso || '');
    return text.length === 10 ? text.slice(5) : text;
  }

  function json(value) {
    try {
      return JSON.stringify(value, null, 2);
    } catch (err) {
      return String(value);
    }
  }

  function uuid() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    // 老浏览器兜底：RFC4122 v4，够用即可。
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (ch) {
      var rnd = Math.random() * 16 | 0;
      var val = ch === 'x' ? rnd : (rnd & 0x3 | 0x8);
      return val.toString(16);
    });
  }

  /* ---------------- 小部件 ---------------- */

  /** 横向占比条。max 为 0 时不画长度，但行还留着。 */
  function bar(label, value, max, valueText) {
    var row = el('div', 'bar-row');
    row.appendChild(el('div', 'bar-label', label));
    var track = el('div', 'bar-track');
    var fill = el('div', 'bar-fill');
    var ratio = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
    fill.style.width = (ratio * 100).toFixed(1) + '%';
    if (ratio <= 0) { fill.className = 'bar-fill is-zero'; }
    track.appendChild(fill);
    row.appendChild(track);
    row.appendChild(el('div', 'bar-val', valueText));
    return row;
  }

  /** 可折叠块，内容为一段 JSON。 */
  function details(summaryText, contentNode, open) {
    var box = el('details', 'block');
    if (open) { box.open = true; }
    var summary = el('summary', null, summaryText);
    box.appendChild(summary);
    var body = el('div', 'block-body');
    body.appendChild(contentNode);
    box.appendChild(body);
    return box;
  }

  function codeBlock(value) {
    var pre = el('pre', 'code');
    pre.textContent = typeof value === 'string' ? value : json(value);
    return pre;
  }

  function kv(key, value) {
    var item = el('div', 'kv-item');
    item.appendChild(el('div', 'kv-k', key));
    item.appendChild(el('div', 'kv-v', value));
    return item;
  }

  function empty(text) {
    return el('p', 'muted empty', text);
  }

  var toastTimer = null;
  function toast(message, isError) {
    var node = $('toast');
    if (!node) {
      node = el('div', 'toast');
      node.id = 'toast';
      document.body.appendChild(node);
    }
    node.textContent = message;
    node.className = 'toast' + (isError ? ' is-error' : '');
    node.hidden = false;
    if (toastTimer) { clearTimeout(toastTimer); }
    toastTimer = setTimeout(function () { node.hidden = true; }, isError ? 5000 : 2600);
  }

  return {
    $: $, el: el, clear: clear, api: api, query: query,
    escapeHtml: escapeHtml, isNum: isNum, int: int, money: money, yuan: yuan,
    num: num, ms: ms, compact: compact, shortDate: shortDate, json: json, uuid: uuid,
    bar: bar, details: details, codeBlock: codeBlock, kv: kv, empty: empty, toast: toast
  };
})();

/* 浏览器里靠上面的全局变量；Node 下（语法/渲染离线校验）走模块导出。 */
if (typeof module !== 'undefined' && module.exports) { module.exports = U; }
