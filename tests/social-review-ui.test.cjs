'use strict';
// Dynamic imports keep this explicit CJS test entry compatible with the
// repository's no-require-imports lint rule without disabling that rule.
(async function main() {
  const {default: test} = await import('node:test');
  const {default: assert} = await import('node:assert/strict');
  const {default: fs} = await import('node:fs');
  const {default: path} = await import('node:path');
  const {default: vm} = await import('node:vm');
  // Evaluate the unchanged classic browser asset independently of package mode.
  const sandbox = {module: {exports: {}}, URL};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../tools/social/review_ui/app.js'), 'utf8'), sandbox, {filename: 'review-app.js'});
  const {makeDecision, safeLink, timestampWarning} = sandbox.module.exports;
  const VERSION = 'a'.repeat(64), ID = '00000000-0000-4000-8000-000000000099';
  function row() { return {active:true,item:{status:'pending',queueVersion:VERSION,candidateKey:'shadow-social:synthetic:revision',candidateFingerprint:'b'.repeat(64)}}; }
  function decide(value = row(), action = 'accepted', actor = 'local-reviewer', note = '仅审核线索') { return makeDecision(value, action, actor, note, ID, VERSION); }

  test('exports exactly the frozen DecisionRequest fields', () => {
    assert.deepEqual(Object.keys(decide()).sort(), ['schemaVersion','kind','requestId','candidateKey','candidateFingerprint','decision','reviewedBy','note','seenQueueVersion'].sort());
    assert.equal(decide().kind,'decision_request'); assert.equal(decide().decision,'accepted');
  });
  test('rejection is distinct and input remains unchanged', () => {
    const value=row(), before=structuredClone(value); assert.equal(decide(value,'rejected').decision,'rejected'); assert.deepEqual(value,before);
  });
  test('history and terminal states cannot export fresh decisions', () => {
    for(const status of ['accepted','rejected']) assert.throws(()=>decide({active:true,item:{...row().item,status}}));
    assert.throws(()=>decide({...row(),active:false}));
  });
  test('actor must be nonblank, trimmed, bounded and not email', () => {
    for(const actor of ['', ' ', ' reviewer', 'x@example.invalid', 'x\ny', 'x'.repeat(161)]) assert.throws(()=>decide(row(),'accepted',actor));
  });
  test('invalid action, note and identity are rejected', () => {
    assert.throws(()=>decide(row(),'promote')); assert.throws(()=>decide(row(),'accepted','reviewer','x'.repeat(601)));
    assert.throws(()=>makeDecision(row(),'accepted','reviewer','', 'bad', VERSION));
    assert.throws(()=>decide({active:true,item:{...row().item,candidateFingerprint:'invalid'}}));
  });
  test('queue version mismatch cannot be silently overwritten', () => {
    assert.throws(()=>makeDecision(row(),'accepted','reviewer','',ID,'c'.repeat(64)));
  });
  test('decision does not invent production or verification flags', () => {
    const result = decide(); for(const key of ['publish','factVerified','companyId','promotionStatus']) assert.equal(Object.hasOwn(result,key),false);
  });
  test('known canonical URLs are accepted without fetching', () => {
    for(const url of ['https://www.bilibili.com/video/BV1abcDEF234','https://www.zhihu.com/question/123/answer/456','https://zhuanlan.zhihu.com/p/123','https://mp.weixin.qq.com/s?__biz=123&mid=1&idx=1','https://m.weibo.cn/detail/123']) assert.equal(safeLink(url),url);
  });
  test('script, credentials, tokens and spoofed hosts are blocked', () => {
    for(const url of ['javascript:alert(1)','http://m.weibo.cn/detail/1','https://u:p@m.weibo.cn/detail/1','https://m.weibo.cn.evil.invalid/detail/1','https://m.weibo.cn/detail/1?token=secret','https://m.weibo.cn/detail/1#x','https://www.zhihu.com/people/person','https://m.weibo.cn:9999/detail/1']) assert.equal(safeLink(url),null);
  });
  test('unknown and missing URLs remain unavailable', () => { for(const value of [null,undefined,{},'','https://unknown.invalid/x']) assert.equal(safeLink(value),null); });
  test('BVID case is preserved', () => { assert.equal(safeLink('https://www.bilibili.com/video/BV1abcDEF234'),'https://www.bilibili.com/video/BV1abcDEF234'); });
  test('XHS source chronology conflict is explicit without changing evidence', () => {
    const doc = {platform:'xhs',publishedPrecision:'second',publishedAt:'2026-10-22T12:00:00+00:00',updatedAt:'2026-10-21T12:00:00+00:00'};
    const before = structuredClone(doc);
    assert.match(timestampWarning(doc), /来源时间矛盾/);
    assert.deepEqual(doc,before);
  });
  test('unknown, day precision and other platforms do not invent a conflict', () => {
    for (const doc of [null, {}, {platform:'wb'}, {platform:'xhs',publishedPrecision:'day',publishedAt:'2026-10-22',updatedAt:'2026-10-21'}]) assert.equal(timestampWarning(doc),null);
  });
  test('equal or later update and invalid timestamps have no chronology warning', () => {
    const doc = {platform:'xhs',publishedPrecision:'second',publishedAt:'2026-10-22T12:00:00+00:00'};
    for (const updatedAt of [null,'invalid','2026-10-22T12:00:00+00:00','2026-10-23T12:00:00+00:00']) assert.equal(timestampWarning({...doc,updatedAt}),null);
  });
})().catch(error => { console.error(error); process.exitCode = 1; });
