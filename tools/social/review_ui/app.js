/* Local-only review UI. Untrusted evidence is rendered as text, never markup. */
(function (global) {
  'use strict';
  const TYPES = {company_discovery: '公司发现', funding: '融资线索', product: '产品线索', technology: '技术线索', listing: '上市线索'};
  const STATES = {pending: '待审核', accepted: '已接受 · 等待一手证据', rejected: '已拒绝'};
  function safeLink(value) {
    if (typeof value !== 'string' || /[\\\s]/.test(value)) return null;
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password || url.port || url.hash) return null;
      const patterns = {
        'mp.weixin.qq.com': /^\/s(?:\/[A-Za-z0-9_-]+)?$/,
        'www.xiaohongshu.com': /^\/(?:explore|discovery\/item)\/[A-Za-z0-9_-]+$/,
        'xiaohongshu.com': /^\/(?:explore|discovery\/item)\/[A-Za-z0-9_-]+$/,
        'm.weibo.cn': /^\/detail\/\d+$/,
        'weibo.com': /^\/\d+\/[A-Za-z0-9]+$/,
        'www.weibo.com': /^\/\d+\/[A-Za-z0-9]+$/,
        'www.bilibili.com': /^\/video\/(?:av\d+|BV[A-Za-z0-9]+)\/?$/,
        'bilibili.com': /^\/video\/(?:av\d+|BV[A-Za-z0-9]+)\/?$/,
        'www.zhihu.com': /^\/(?:question\/\d+\/answer\/\d+|zvideo\/\d+)$/,
        'zhihu.com': /^\/(?:question\/\d+\/answer\/\d+|zvideo\/\d+)$/,
        'zhuanlan.zhihu.com': /^\/p\/\d+$/
      };
      if (!patterns[url.hostname] || !patterns[url.hostname].test(url.pathname)) return null;
      const permitted = url.hostname === 'mp.weixin.qq.com' ? ['__biz', 'mid', 'idx'] : [];
      if (Array.from(url.searchParams.keys()).some(k => !permitted.includes(k))) return null;
      return url.href;
    } catch (_) { return null; }
  }
  function makeDecision(row, action, actor, note, requestId, queueVersion) {
    const item = row && row.item;
    if (!item || row.active !== true || item.status !== 'pending') throw new Error('只能审核当前待处理版本');
    if (!['accepted', 'rejected'].includes(action)) throw new Error('决定类型无效');
    if (typeof actor !== 'string' || !actor.trim() || actor !== actor.trim() || actor.length > 160 || /[@\r\n]/.test(actor)) throw new Error('请输入有效的审核者标记，不使用邮箱');
    if (typeof note !== 'string' || note.length > 600) throw new Error('备注过长');
    if (!/^[0-9a-f-]{36}$/.test(requestId) || !/^[0-9a-f]{64}$/.test(queueVersion) || item.queueVersion !== queueVersion) throw new Error('队列版本无效，请刷新');
    if (!/^[0-9a-f]{64}$/.test(item.candidateFingerprint) || typeof item.candidateKey !== 'string' || !item.candidateKey.startsWith('shadow-social:')) throw new Error('候选指纹无效');
    return {schemaVersion: 1, kind: 'decision_request', requestId, candidateKey: item.candidateKey,
      candidateFingerprint: item.candidateFingerprint, decision: action, reviewedBy: actor,
      note, seenQueueVersion: queueVersion};
  }
  function timestampWarning(doc) {
    if (!doc || doc.platform !== 'xhs' || doc.publishedPrecision !== 'second' ||
        typeof doc.publishedAt !== 'string' || typeof doc.updatedAt !== 'string') return null;
    const published = Date.parse(doc.publishedAt), updated = Date.parse(doc.updatedAt);
    return Number.isFinite(published) && Number.isFinite(updated) && updated < published
      ? '来源时间矛盾：记录的更新时间早于发布时间。两者按原值保留，不能据此确认事件发生时间。'
      : null;
  }
  const api = {safeLink, makeDecision, timestampWarning};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document === 'undefined') return;
  global.VCIQReview = api;
  const $ = id => document.getElementById(id);
  const state = {offset: 0, next: null, version: '', pending: null};
  function node(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function field(parent, label, value) {
    const p = node('p'); p.append(node('strong', label + '：'), node('span', value || '未知')); parent.append(p);
  }
  function begin(row, action) {
    state.pending = {row, action, version: state.version};
    $('decision-label').textContent = (action === 'accepted' ? '接受为待核验线索：' : '拒绝线索：') + (row.snapshot.observation.title || '无标题');
    $('ack').checked = false; $('dialog-error').textContent = ''; $('decision-dialog').showModal();
  }
  function renderRow(row) {
    const item = row.item, doc = row.snapshot.observation;
    const card = node('article', undefined, 'card');
    const top = node('div', undefined, 'card-top');
    top.append(node('span', TYPES[item.leadType] || item.leadType, 'badge'), node('span', STATES[item.status] || item.status, 'status'));
    card.append(top, node('h2', doc.title || '无标题材料'));
    const warning = timestampWarning(doc);
    if (warning) { const p = node('p'); p.append(node('strong', warning)); card.append(p); }
    const claim = node('blockquote'); item.claims.forEach(text => claim.append(node('p', text))); card.append(claim);
    const details = node('details'); details.append(node('summary', '查看固定证据与来源'));
    field(details, '平台 / 内容类型', doc.platform + ' / ' + doc.contentType);
    field(details, '发表时间', doc.publishedAt); field(details, '证据观察时间', doc.observedAt);
    field(details, '来源更新时间', doc.updatedAt);
    field(details, '文本范围', doc.textScope); field(details, '摘录', doc.excerpt);
    field(details, '主体消歧', item.subject.resolution === 'ambiguous' ? '存在同名或多个候选，未绑定' : '未确认主体身份');
    const suggestions = row.snapshot.companySuggestions || [];
    field(details, '名称匹配候选（不是身份确认）', suggestions.map(s => s.companyName + ' [' + s.companyId + ']').join('；'));
    field(details, '内容哈希', item.evidence[0].contentHash);
    field(details, '候选指纹', item.candidateFingerprint);
    const href = safeLink(item.evidence[0].canonicalUrl);
    if (href) { const a = node('a', '打开原始链接（可访问性未保证）'); a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; details.append(a); }
    else details.append(node('p', '没有可安全打开的规范链接。'));
    if (row.decision) { field(details, '审核者', row.decision.request.reviewedBy); field(details, '审核备注', row.decision.request.note); field(details, '记录时间', row.decision.decidedAt); }
    card.append(details);
    if (row.active && item.status === 'pending') {
      const actions = node('div', undefined, 'actions');
      for (const [action, label] of [['accepted', '接受为线索'], ['rejected', '拒绝']]) {
        const button = node('button', label); button.type = 'button'; button.addEventListener('click', () => begin(row, action)); actions.append(button);
      }
      card.append(actions);
    }
    return card;
  }
  async function refresh() {
    $('refresh').disabled = true; $('message').textContent = ''; $('items').replaceChildren();
    $('previous').disabled = true; $('next').disabled = true;
    try {
      const response = await fetch('/api/queue?offset=' + state.offset + '&limit=25&history=' + ($('scope').value === 'history'), {cache: 'no-store', credentials: 'omit'});
      if (!response.ok) throw new Error('队列不可用，请检查本地数据库与服务');
      const value = await response.json();
      if (!value.ok || value.mode !== 'shadow' || value.publish !== false || !Array.isArray(value.items)) throw new Error('队列结构无效');
      state.version = value.queueVersion; state.next = value.nextOffset;
      $('summary').textContent = '本范围共 ' + value.total + ' 条 · 本页 ' + value.items.length + ' 条';
      $('page').textContent = '第 ' + (Math.floor(state.offset / 25) + 1) + ' 页';
      if (!value.items.length) $('items').append(node('p', '暂无候选。先完成内容入库，再执行 review_cli sync --apply。', 'empty'));
      else value.items.forEach(row => $('items').append(renderRow(row)));
      $('previous').disabled = state.offset === 0; $('next').disabled = state.next === null;
    } catch (_) { $('message').textContent = '读取失败。未执行任何写入；请检查服务状态并重试。'; $('summary').textContent = '队列未加载'; }
    finally { $('refresh').disabled = false; }
  }
  $('refresh').addEventListener('click', refresh);
  $('scope').addEventListener('change', () => { state.offset = 0; refresh(); });
  $('previous').addEventListener('click', () => { state.offset = Math.max(0, state.offset - 25); refresh(); });
  $('next').addEventListener('click', () => { if (state.next !== null) { state.offset = state.next; refresh(); } });
  $('cancel').addEventListener('click', () => $('decision-dialog').close());
  $('export').addEventListener('click', () => {
    try {
      if (!$('ack').checked || !state.pending) throw new Error('请先确认审核边界');
      const {row, action, version} = state.pending;
      const request = makeDecision(row, action, $('reviewer').value, $('note').value, crypto.randomUUID(), version);
      const blob = new Blob([JSON.stringify(request, null, 2) + '\n'], {type: 'application/json'});
      const url = URL.createObjectURL(blob), a = node('a'); a.href = url; a.download = 'decision-' + request.requestId + '.json';
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      $('decision-dialog').close(); $('message').textContent = '决定文件已导出，但尚未应用。请通过 CLI 校验并记录，再刷新队列。';
    } catch (error) { $('dialog-error').textContent = error.message; }
  });
  refresh();
})(typeof globalThis !== 'undefined' ? globalThis : this);
