import assert from 'node:assert/strict';
import test from 'node:test';
import { newManagerCohort as cohort, newManagerCohortSummary } from '../lib/innovation-new-managers';

test('the fixed media cohort reconciles independently to 35 and 15 after June 5',()=>{
  const summary=newManagerCohortSummary();
  assert.equal(summary.total,35); assert.equal(summary.afterJune5,15);
  assert.deepEqual(summary.months.map(row=>row.count),[3,5,3,6,3,0,4,10,1]);
  assert.equal(new Set(cohort.managers.map(row=>row.registrationNumber)).size,35);
  assert.deepEqual(['市场化','CVC','国资'].map(category=>cohort.managers.filter(row=>row.mediaCategory===category).length),[18,3,14]);
});
test('every reviewed profile has provenance without promoting product counts into cashflows',()=>{
  for(const row of cohort.managers){
    assert.ok(row.sourceUrl.startsWith('https://gs.amac.org.cn/amac-infodisc/res/pof/manager/'));
    assert.match(row.registrationNumber,/^P\d{7}$/); assert.equal(row.registrationDate,row.reportedRegistrationDate);
    assert.ok(row.shareholders.length>0); assert.ok(row.executives.length>0);
    assert.ok(row.legalName.endsWith('公司')); assert.equal(row.checkedAt,cohort.checkedAt);
    assert.equal(row.fundraisingStatus,'unknown'); assert.equal(row.investmentStatus,'unknown'); assert.equal(row.realizedExitStatus,'unknown');
    const sum=row.shareholders.reduce((sum,holder)=>sum+parseFloat(holder.subscribedPercent),0);
    assert.ok(Math.abs(sum-100)<.1,`${row.legalName}: ${sum}`);
  }
});
