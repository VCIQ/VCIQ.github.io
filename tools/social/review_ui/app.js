'use strict';
const labels = {company_discovery:'公司发现', funding:'融资', product:'产品', technology:'技术', listing:'上市'};
let snapshot = null;
function node(tag, value, className) {
  const element = document.createElement(tag);
  if (value !== undefined) element.textContent = value;
  if (className) element.className = className;
  return element;
}
function exportDecision(item, action, note) {
  const actor = document.getElementById('actor').value.trim();
  if (!actor || actor.includes('@')) { document.getElementById('summary').textContent = '请填写非邮箱的审核人标签。'; return; }
  const request = {schemaVersion:1, kind:'decision_request', requestId:crypto.randomUUID(), candidateKey:item.candidateKey,
    candidateFingerprint:item.candidateFingerprint, decision:action, reviewedBy:actor, note:note.value,
    seenQueueVersion:snapshot.queueVersion};
  const blob = new Blob([JSON.stringify(request, null, 2) + '\n'], {type:'application/json'});
  const url = URL.createObjectURL(blob);
  const anchor = node('a'); anchor.href = url; anchor.download = 'shadow-decision-' + request.requestId + '.json';
  document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function render() {
  const target = document.getElementById('queue'); target.replaceChildren();
  if (!snapshot) return;
  const type = document.getElementById('type').value, status = document.getElementById('status').value;
  const rows = snapshot.candidates.filter(item => (!type || item.leadType === type) && (!status || item.status === status));
  document.getElementById('summary').textContent = `当前显示 ${rows.length} / ${snapshot.candidates.length} 条。真实来源尚需核验；此处不表示融资或上市事实已经确认。`;
  for (const item of rows) {
    const card = node('article', undefined, 'card');
    card.append(node('h2', `${labels[item.leadType] || item.leadType} · ${item.subject.companyName || '主体待消歧'}`));
    card.append(node('p', `状态：${item.status} / ${item.promotionStatus}；主体识别：${item.subject.resolution}`, 'meta'));
    for (const claim of item.claims) card.append(node('blockquote', claim));
    for (const evidence of item.evidence) {
      const section = node('section'); section.append(node('p', `证据：${evidence.signalId}；发表日期：${evidence.publishedAt || '未知'}；待交叉验证`));
      if (evidence.canonicalUrl) {
        const link = node('a', '手动打开原始链接（可访问性未经保证）');
        const url = new URL(evidence.canonicalUrl);
        if (url.protocol === 'https:' && !url.username && !url.password) {
          link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; section.append(link);
        }
      }
      card.append(section);
    }
    if (item.status === 'pending') {
      const note = node('textarea'); note.maxLength = 600; note.placeholder = '审核说明；不得填写账号密码或 Cookie'; note.setAttribute('aria-label','审核说明');
      const actions = node('div', undefined, 'actions');
      for (const [action, label] of [['accepted','导出接受决定'],['rejected','导出拒绝决定']]) {
        const button = node('button', label); button.addEventListener('click', () => exportDecision(item, action, note)); actions.append(button);
      }
      card.append(note, actions);
    }
    card.append(node('p', `证据指纹：${item.candidateFingerprint}`, 'fingerprint'));
    target.append(card);
  }
}
async function refresh() {
  try {
    const response = await fetch('/api/queue', {cache:'no-store', credentials:'omit'});
    if (!response.ok) throw new Error('snapshot');
    const data = await response.json();
    if (data.mode !== 'shadow' || data.publish !== false || !Array.isArray(data.candidates)) throw new Error('shape');
    snapshot = data; render();
  } catch (_) { document.getElementById('summary').textContent = '无法读取有效队列。请先在本机生成影子审核队列。'; }
}
document.getElementById('refresh').addEventListener('click', refresh);
document.getElementById('type').addEventListener('change', render);
document.getElementById('status').addEventListener('change', render);
refresh();
