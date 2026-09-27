/* 页面装配：读健康检查拿到数据区间，接好三个标签，处理标签切换。 */
'use strict';

(function () {

  var TITLES = { dash: '经营看板', qa: '问答', debug: '调试面板' };

  function switchTab(name) {
    var tabs = document.querySelectorAll('#tabs .tab');
    Array.prototype.forEach.call(tabs, function (tab) {
      tab.classList.toggle('is-active', tab.getAttribute('data-tab') === name);
    });
    var views = document.querySelectorAll('.view');
    Array.prototype.forEach.call(views, function (view) {
      view.classList.toggle('is-active', view.id === 'view-' + name);
    });
    window.scrollTo(0, 0);
    if (name === 'dash') { Dashboard.drawChart(); }
    if (TITLES[name]) { document.title = TITLES[name] + ' · 经营看板'; }
  }

  function bindTabs() {
    var tabs = document.querySelectorAll('#tabs .tab');
    Array.prototype.forEach.call(tabs, function (tab) {
      tab.addEventListener('click', function () {
        switchTab(tab.getAttribute('data-tab'));
      });
    });
  }

  function describeHealth(health) {
    var period = health.data_period || {};
    var parts = [
      '今天 ' + (health.today || '—'),
      '数据区间 ' + (period.start || '—') + ' ~ ' + (period.end || '—'),
      '模式 ' + (health.llm_mode || '—'),
      '知识库 ' + (health.kb_docs === undefined ? '—' : health.kb_docs) + ' 篇 / '
        + (health.kb_chunks === undefined ? '—' : health.kb_chunks) + ' 段',
      '有效销售行 ' + U.int(health.valid_sales_rows)
    ];
    return parts.join(' · ');
  }

  function boot() {
    bindTabs();
    Chat.init();
    Trace.init();

    // 「看调试」：切到标签 3 并加载对应 trace
    document.addEventListener('open-trace', function (event) {
      var traceId = event.detail && event.detail.traceId;
      switchTab('debug');
      Trace.load(traceId);
    });

    U.api('/api/health').then(function (health) {
      U.$('health-line').textContent = describeHealth(health || {});
      return Dashboard.init(health || {});
    }).catch(function (error) {
      U.$('health-line').textContent = '/api/health 调用失败：' + error.message;
      U.toast('后端健康检查失败：' + error.message, true);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
