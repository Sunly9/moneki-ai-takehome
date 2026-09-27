/* 标签 3：调试面板。数据全部来自 GET /api/trace/{trace_id}；trace_id 不存在时后端返回 404。 */
'use strict';

var Trace = (function () {

  function findStep(steps, name) {
    for (var i = 0; i < steps.length; i += 1) {
      if (steps[i] && steps[i].step === name) { return steps[i]; }
    }
    return null;
  }

  function detailOf(step) {
    return (step && step.detail && typeof step.detail === 'object') ? step.detail : {};
  }

  function renderErrors(errors) {
    var box = U.el('div', 'error-box');
    box.appendChild(U.el('div', 'e-line', '本次问答发生了 ' + errors.length + ' 个错误'));
    errors.forEach(function (item, index) {
      var text = '[' + (index + 1) + '] ' + (item.where || '') + ' · '
        + (item.type || '') + '：' + (item.message || '');
      box.appendChild(U.el('div', 'e-line', text));
      if (item.traceback) {
        box.appendChild(U.details('堆栈', U.codeBlock(item.traceback), false));
      }
    });
    return box;
  }

  function renderHead(trace) {
    var card = U.el('div', 'card');
    var grid = U.el('div', 'trace-grid');
    var fields = [
      ['trace_id', trace.trace_id || '—'],
      ['session_id', trace.session_id || '（无）'],
      ['开始时间', trace.started_at || '—'],
      ['总耗时', U.ms(trace.total_ms)]
    ];
    fields.forEach(function (pair) {
      var cell = U.el('div');
      cell.appendChild(U.el('div', 't-k', pair[0]));
      cell.appendChild(U.el('div', 't-v', pair[1]));
      grid.appendChild(cell);
    });
    card.appendChild(grid);
    card.appendChild(U.el('div', 't-k', '问题'));
    card.appendChild(U.el('div', 't-v', trace.question || '（空问题）'));
    if (trace.errors && trace.errors.length) { card.appendChild(renderErrors(trace.errors)); }
    return card;
  }

  function renderPlan(planDetail) {
    var section = U.el('div', 'section');
    section.appendChild(U.el('h3', null, '① 改写后的检索查询'));
    var grid = U.el('div', 'trace-grid');
    var fields = [
      ['search_query', planDetail.search_query || '（空）'],
      ['standalone_question', planDetail.standalone_question || '（与问题相同）'],
      ['intent / kind', (planDetail.intent || '—') + ' / ' + (planDetail.kind || '—')],
      ['store_id', planDetail.store_id || '（全部）'],
      ['product_id', planDetail.product_id || '（全部）'],
      ['metric', planDetail.metric || '—'],
      ['window', planDetail.window ? (planDetail.window[0] + ' ~ ' + planDetail.window[1]) : '（未指定）'],
      ['compare_window', planDetail.compare_window
        ? (planDetail.compare_window[0] + ' ~ ' + planDetail.compare_window[1]) : '（无）'],
      ['as_of / year', (planDetail.as_of || '—') + ' / ' + (planDetail.year === null || planDetail.year === undefined ? '—' : planDetail.year)],
      ['needs_data / needs_docs', String(!!planDetail.needs_data) + ' / ' + String(!!planDetail.needs_docs)]
    ];
    fields.forEach(function (pair) {
      var cell = U.el('div');
      cell.appendChild(U.el('div', 't-k', pair[0]));
      cell.appendChild(U.el('div', 't-v', pair[1]));
      grid.appendChild(cell);
    });
    section.appendChild(grid);
    if (planDetail.refusal) {
      section.appendChild(U.el('div', 'e-line', '拒绝理由：' + planDetail.refusal));
    }
    if (planDetail.notes && planDetail.notes.length) {
      var list = U.el('ul', 'warn-list');
      planDetail.notes.forEach(function (note) { list.appendChild(U.el('li', null, note)); });
      section.appendChild(list);
    }
    section.appendChild(U.details('plan 原始 JSON', U.codeBlock(planDetail), false));
    return section;
  }

  function renderSearch(searchDetail) {
    var section = U.el('div', 'section');
    var hits = searchDetail.hits || [];
    var filtered = searchDetail.filtered || [];
    section.appendChild(U.el('h3', null,
      '② 检索片段（' + hits.length + ' 条命中，' + filtered.length + ' 条被过滤）'));

    var stats = U.el('div', 'trace-grid');
    stats.appendChild(U.kv('实际检索词', searchDetail.query || '（空）'));
    stats.appendChild(U.kv('同义扩写', (searchDetail.expansions || []).join('、') || '（无）'));
    stats.appendChild(U.kv('覆盖率', U.num(searchDetail.coverage, 3)));
    section.appendChild(stats);

    if (!hits.length) {
      section.appendChild(U.empty('这次检索没有任何片段命中。'));
    } else {
      var maxScore = hits.reduce(function (acc, hit) {
        return Math.max(acc, Number(hit.score) || 0);
      }, 0);
      hits.forEach(function (hit) {
        var row = U.el('div', 'hit-row');
        var idBox = U.el('div', 'h-id');
        idBox.appendChild(U.el('div', null, (hit.doc_id || '?') + ' / ' + (hit.chunk_id || '?')));
        if (hit.padded) {
          idBox.appendChild(U.el('span', 'tag tag-pad', '凑数补齐 padded'));
        }
        row.appendChild(idBox);

        var track = U.el('div', 'h-track');
        var fill = U.el('div', 'h-fill' + (hit.padded ? ' is-padded' : ''));
        var ratio = maxScore > 0 ? Math.max(0, Math.min(1, (Number(hit.score) || 0) / maxScore)) : 0;
        fill.style.width = (ratio * 100).toFixed(1) + '%';
        track.appendChild(fill);
        row.appendChild(track);

        row.appendChild(U.el('div', 'h-score', U.num(hit.score, 4)));
        section.appendChild(row);
        if (hit.dropped_instructions && hit.dropped_instructions.length) {
          section.appendChild(U.el('div', 'sub',
            '已经丢弃的疑似指令文本 ' + hit.dropped_instructions.length + ' 处（不作为指令执行）'));
        }
      });
    }

    if (filtered.length) {
      section.appendChild(U.el('div', 'sub', '被元数据过滤掉的片段'));
      var table = U.el('table', 'table');
      var thead = U.el('thead');
      var headRow = U.el('tr');
      headRow.appendChild(U.el('th', null, 'doc_id'));
      headRow.appendChild(U.el('th', null, '过滤原因'));
      thead.appendChild(headRow);
      table.appendChild(thead);
      var tbody = U.el('tbody');
      filtered.forEach(function (item) {
        var tr = U.el('tr');
        tr.appendChild(U.el('td', null, item.doc_id || '?'));
        tr.appendChild(U.el('td', null, item.reason || '（未给原因）'));
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      section.appendChild(table);
    } else {
      section.appendChild(U.el('div', 'sub', '没有片段被元数据过滤掉。'));
    }
    return section;
  }

  function renderTools(steps) {
    var section = U.el('div', 'section');
    var tools = steps.filter(function (step) { return step.step === 'tool'; });
    section.appendChild(U.el('h3', null, '③ 工具调用 / SQL（' + tools.length + ' 次）'));
    if (!tools.length) {
      section.appendChild(U.empty('这次回答没有执行任何工具调用（纯文档回答或直接拒答）。'));
      return section;
    }
    tools.forEach(function (step, index) {
      var detail = detailOf(step);
      var tool = detail.tool || '（未知工具）';
      var title = '#' + (index + 1) + ' ' + tool + ' · 耗时 ' + U.ms(step.took_ms);
      var box = U.el('div');
      box.appendChild(U.el('div', 'sub', 'params'));
      box.appendChild(U.codeBlock(detail.params === undefined ? {} : detail.params));
      box.appendChild(U.el('div', 'sub', 'took_ms / at_ms'));
      box.appendChild(U.codeBlock({ took_ms: step.took_ms, at_ms: step.at_ms }));
      if (detail.result !== undefined) {
        box.appendChild(U.el('div', 'sub', 'result'));
        box.appendChild(U.codeBlock(detail.result));
      }
      section.appendChild(U.details(title, box, false));
    });
    return section;
  }

  function renderLlm(llmCalls) {
    var section = U.el('div', 'section');
    section.appendChild(U.el('h3', null, '④ 大模型调用（' + llmCalls.length + ' 次）'));
    if (!llmCalls.length) {
      section.appendChild(U.empty('本次没有调用大模型（mock 模式下由本地模板渲染回答）。'));
      return section;
    }
    llmCalls.forEach(function (call, index) {
      var meta = U.el('div', 'trace-grid');
      var fields = [
        ['endpoint', call.endpoint || '—'],
        ['model', call.model || '—'],
        ['messages / tools', (call.messages === undefined ? '—' : call.messages) + ' / '
          + (call.tools === undefined ? '—' : call.tools)],
        ['status', call.status === undefined ? '—' : call.status],
        ['finish_reason', call.finish_reason || '—'],
        ['took_ms', U.ms(call.took_ms)],
        ['tool_calls', (call.tool_calls || []).join('、') || '（无）'],
        ['error', call.error ? (call.error + (call.detail ? ('：' + call.detail) : '')) : '（无）']
      ];
      fields.forEach(function (pair) {
        var cell = U.el('div');
        cell.appendChild(U.el('div', 't-k', pair[0]));
        cell.appendChild(U.el('div', 't-v', pair[1]));
        gridAppend(meta, cell);
      });

      var box = U.el('div');
      box.appendChild(meta);
      box.appendChild(U.el('div', 'sub', '发给大模型的最终提示词（messages 序列化）'));
      box.appendChild(U.codeBlock(call.prompt === undefined ? '（trace 里没有记录 prompt）' : call.prompt));
      box.appendChild(U.el('div', 'sub', '模型原始输出 raw_content'
        + (call.content_chars === undefined ? '' : ('（' + call.content_chars + ' 字）'))));
      box.appendChild(U.codeBlock(call.raw_content === undefined ? '（没有正文）' : call.raw_content));
      if (call.raw_reasoning) {
        box.appendChild(U.el('div', 'sub', '思考过程 raw_reasoning'));
        box.appendChild(U.codeBlock(call.raw_reasoning));
      }
      if (call.usage) {
        box.appendChild(U.el('div', 'sub', 'usage'));
        box.appendChild(U.codeBlock(call.usage));
      }
      section.appendChild(U.details('调用 #' + (index + 1) + '：' + (call.model || '（未知模型）'), box, index === 0));
    });
    return section;
  }

  function gridAppend(grid, cell) { grid.appendChild(cell); }

  function renderSteps(steps, totalMs) {
    var section = U.el('div', 'section');
    section.appendChild(U.el('h3', null, '⑤ 每一步耗时（总耗时 ' + U.ms(totalMs) + '）'));
    if (!steps.length) {
      section.appendChild(U.empty('这次 trace 里没有记录任何步骤。'));
      return section;
    }
    var maxTook = steps.reduce(function (acc, step) {
      return Math.max(acc, Number(step.took_ms) || 0);
    }, 0);
    steps.forEach(function (step) {
      var row = U.el('div', 'step-row');
      row.appendChild(U.el('div', 's-name', step.step || '?'));
      var track = U.el('div', 's-bar');
      var fill = U.el('div', 's-fill');
      var took = Number(step.took_ms) || 0;
      fill.style.width = (maxTook > 0 ? (took / maxTook * 100) : 0).toFixed(1) + '%';
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(U.el('div', 's-ms', (step.took_ms === null || step.took_ms === undefined)
        ? '—' : U.ms(step.took_ms)));
      section.appendChild(row);

      var detail = step.detail;
      if (detail !== undefined && detail !== null) {
        var isEmptyObject = typeof detail === 'object'
          && !Array.isArray(detail) && Object.keys(detail).length === 0;
        if (!isEmptyObject) {
          section.appendChild(U.details(
            'at_ms ' + (step.at_ms === undefined ? '—' : step.at_ms) + ' · detail',
            U.codeBlock(detail), false));
        }
      }
    });
    return section;
  }

  function render(trace) {
    var host = U.clear(U.$('trace-body'));
    var steps = trace.steps || [];
    var planDetail = detailOf(findStep(steps, 'plan'));
    var searchDetail = detailOf(findStep(steps, 'search'));

    host.appendChild(renderHead(trace));

    var body = U.el('div', 'card');
    if (Object.keys(planDetail).length) {
      body.appendChild(renderPlan(planDetail));
    } else {
      body.appendChild(U.el('h3', null, '① 改写后的检索查询'));
      body.appendChild(U.empty('这次 trace 里没有 plan 步骤。'));
    }
    body.appendChild(renderSearch(searchDetail));
    body.appendChild(renderTools(steps));
    body.appendChild(renderLlm(trace.llm_calls || []));
    body.appendChild(renderSteps(steps, trace.total_ms));
    host.appendChild(body);

    var raw = U.el('div', 'card');
    raw.appendChild(U.details('完整 trace JSON（原始返回）', U.codeBlock(trace), false));
    host.appendChild(raw);
  }

  function load(traceId) {
    var id = String(traceId || '').trim();
    if (!id) {
      U.toast('先填一个 trace_id', true);
      return Promise.resolve();
    }
    U.$('trace-input').value = id;
    var host = U.clear(U.$('trace-body'));
    host.appendChild(U.empty('正在加载 ' + id + ' …'));
    var button = U.$('btn-load-trace');
    button.disabled = true;

    return U.api('/api/trace/' + encodeURIComponent(id)).then(function (payload) {
      if (!payload || typeof payload !== 'object') {
        host.textContent = '';
        host.appendChild(U.empty('没有这个 trace_id：' + id));
        return;
      }
      render(payload);
    }).catch(function (error) {
      host.textContent = '';
      if (error.status === 404) {
        var box = U.el('div', 'card');
        box.appendChild(U.el('div', 'e-line', '没有这个 trace_id：' + id));
        box.appendChild(U.el('div', 'muted',
          '服务端返回 404。trace 只保留最近若干条，重启服务或超出容量后会查不到。'));
        host.appendChild(box);
        return;
      }
      var fail = U.el('div', 'card');
      fail.appendChild(U.el('div', 'e-line', '加载失败：' + error.message));
      host.appendChild(fail);
    }).then(function () {
      button.disabled = false;
    });
  }

  function init() {
    U.$('btn-load-trace').addEventListener('click', function () { load(U.$('trace-input').value); });
    U.$('trace-input').addEventListener('keydown', function (event) {
      if (event.key === 'Enter') { load(U.$('trace-input').value); }
    });
  }

  return {
    init: init,
    load: load,
    // 离线校验用：直接喂真实接口返回，确认渲染不炸。
    __probe: {
      render: render, renderHead: renderHead, renderPlan: renderPlan,
      renderSearch: renderSearch, renderTools: renderTools, renderLlm: renderLlm,
      renderSteps: renderSteps, findStep: findStep, detailOf: detailOf
    }
  };
})();

/* 浏览器里靠上面的全局变量；Node 下（语法/渲染离线校验）走模块导出。 */
if (typeof module !== 'undefined' && module.exports) { module.exports = Trace; }
