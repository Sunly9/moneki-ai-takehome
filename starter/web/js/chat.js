/* 标签 2：问答。session_id 由前端生成，同一个页面内保持不变，直到点「新会话」。 */
'use strict';

var Chat = (function () {

  var TYPE_LABELS = {
    data: '数据回答',
    doc: '文档回答',
    hybrid: '数据 + 文档',
    refusal: '拒答',
    clarify: '需要澄清'
  };

  var state = { sessionId: '', busy: false };

  function newSession() {
    state.sessionId = U.uuid();
    U.$('qa-session').textContent = '会话 ' + state.sessionId.slice(0, 8) + '…';
    U.clear(U.$('qa-thread'));
    U.$('qa-thread').appendChild(U.empty('新会话已开始。同一个会话里的连续追问会带上上一轮上下文。'));
  }

  function badge(answerType) {
    var type = String(answerType || '');
    var known = Object.prototype.hasOwnProperty.call(TYPE_LABELS, type);
    var node = U.el('span', 'badge ' + (known ? ('badge-' + type) : 'badge-other'));
    node.textContent = known ? (TYPE_LABELS[type] + ' · ' + type) : (type || '未知类型');
    return node;
  }

  /** 把 [KB-013] 这类编号标成小标签；正文其余部分原样作为文本节点，不解析 HTML。 */
  function answerBody(text) {
    var host = U.el('div', 'body');
    var source = String(text === undefined || text === null ? '' : text);
    var pattern = /(\[KB-\d+\])/g;
    var last = 0;
    var match = pattern.exec(source);
    while (match) {
      if (match.index > last) {
        host.appendChild(document.createTextNode(source.slice(last, match.index)));
      }
      host.appendChild(U.el('span', 'tag', match[1]));
      last = match.index + match[1].length;
      match = pattern.exec(source);
    }
    if (last < source.length) {
      host.appendChild(document.createTextNode(source.slice(last)));
    }
    if (!source) { host.appendChild(document.createTextNode('（空回答）')); }
    return host;
  }

  function citationsBlock(citations) {
    if (!citations || !citations.length) { return null; }
    var body = U.el('div');
    citations.forEach(function (item) {
      var cite = U.el('div', 'cite');
      cite.appendChild(U.el('div', 'doc', item.doc_id || '（无编号）'));
      cite.appendChild(U.el('div', 'quote', item.quote || '（无引文）'));
      body.appendChild(cite);
    });
    return U.details('引用原文（' + citations.length + ' 条）', body, false);
  }

  function evidenceBlock(evidence) {
    if (!evidence || !evidence.length) { return null; }
    var body = U.el('div');
    evidence.forEach(function (item, index) {
      var title = '工具 ' + (index + 1) + '：' + (item.tool || '（未知工具）');
      var inner = U.el('div');
      var head = U.el('div', 'sub', 'params');
      inner.appendChild(head);
      inner.appendChild(U.codeBlock(item.params === undefined ? {} : item.params));
      inner.appendChild(U.el('div', 'sub', 'result'));
      inner.appendChild(U.codeBlock(item.result === undefined ? {} : item.result));
      body.appendChild(U.details(title, inner, false));
    });
    return U.details('数据证据（' + evidence.length + ' 条工具调用）', body, false);
  }

  function renderTurn(payload, question) {
    var thread = U.$('qa-thread');
    var placeholder = thread.querySelector('.empty');
    if (placeholder) { placeholder.remove(); }

    var turn = U.el('div', 'turn');

    var q = U.el('div', 'turn-q');
    q.appendChild(U.el('span', 'who', '问'));
    q.appendChild(U.el('span', 'text', question));
    turn.appendChild(q);

    var a = U.el('div', 'turn-a');
    var meta = U.el('div', 'turn-meta');
    meta.appendChild(badge(payload.answer_type));

    var traceId = payload.trace_id || '';
    if (traceId) {
      meta.appendChild(U.el('span', 'muted', 'trace ' + traceId));
      var link = U.el('button', 'link-btn', '看调试');
      link.type = 'button';
      link.addEventListener('click', function () {
        document.dispatchEvent(new CustomEvent('open-trace', { detail: { traceId: traceId } }));
      });
      meta.appendChild(link);
    }
    a.appendChild(meta);
    a.appendChild(answerBody(payload.answer));

    var citations = citationsBlock(payload.citations);
    if (citations) { a.appendChild(citations); }
    var evidence = evidenceBlock(payload.data_evidence);
    if (evidence) { a.appendChild(evidence); }
    if (!citations && !evidence) {
      a.appendChild(U.el('div', 'muted', '本次回答没有引用文档，也没有工具取数。'));
    }

    turn.appendChild(a);
    thread.appendChild(turn);
    turn.scrollIntoView({ block: 'nearest' });
  }

  function ask() {
    if (state.busy) { return Promise.resolve(); }
    var input = U.$('qa-input');
    var question = input.value.trim();
    if (!question) {
      U.toast('先输入一个问题', true);
      return Promise.resolve();
    }
    state.busy = true;
    var button = U.$('btn-ask');
    button.disabled = true;
    button.textContent = '思考中…';

    var thread = U.$('qa-thread');
    var placeholder = thread.querySelector('.empty');
    if (placeholder) { placeholder.remove(); }
    var pending = U.el('div', 'turn');
    pending.appendChild(U.el('div', 'turn-q', '问：' + question));
    pending.appendChild(U.el('div', 'muted', '正在检索与取数…'));
    thread.appendChild(pending);

    return U.api('/api/chat', {
      method: 'POST',
      body: { session_id: state.sessionId, question: question }
    }).then(function (payload) {
      pending.remove();
      renderTurn(payload || {}, question);
      input.value = '';
    }).catch(function (error) {
      pending.remove();
      U.toast('提问失败：' + error.message, true);
      thread.appendChild(U.el('div', 'muted', '这次提问失败了：' + error.message));
    }).then(function () {
      state.busy = false;
      button.disabled = false;
      button.textContent = '发送';
    });
  }

  function init() {
    newSession();
    U.$('btn-ask').addEventListener('click', ask);
    U.$('btn-new-session').addEventListener('click', function () {
      newSession();
      U.toast('已开始新会话');
    });
    U.$('qa-input').addEventListener('keydown', function (event) {
      if (event.key === 'Enter') { ask(); }
    });
  }

  /** 支持从外部（比如看板）直接带一个问题过来。 */
  function focusWith(question) {
    if (question) { U.$('qa-input').value = question; }
    U.$('qa-input').focus();
  }

  return {
    init: init,
    ask: ask,
    focusWith: focusWith,
    sessionId: function () { return state.sessionId; },
    // 离线校验用：直接喂真实接口返回，确认渲染不炸。
    __probe: {
      renderTurn: renderTurn, badge: badge, citationsBlock: citationsBlock,
      evidenceBlock: evidenceBlock, answerBody: answerBody
    }
  };
})();

/* 浏览器里靠上面的全局变量；Node 下（语法/渲染离线校验）走模块导出。 */
if (typeof module !== 'undefined' && module.exports) { module.exports = Chat; }
