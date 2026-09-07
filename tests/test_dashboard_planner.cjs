const {test} = require('node:test');
const assert = require('node:assert/strict');
const {fresh, plan} = require('../site/planner.js');
const data={status:'ready',decision_at:'2026-09-07T10:00:00Z',price_date:'2026-09-07',max_price_age_hours:48,rules:{minimum_position_eur:20,min_weight_change:.02}};
const asset={target_weight:.25,reference_price_usd:100};
test('stale, failed, missing and future data cannot be fresh',()=>{
  assert.equal(fresh(data,Date.parse('2026-09-07T11:00:00Z')),true);
  for(const d of [{...data,status:'unavailable'},{...data,price_date:'2026-09-01'},{...data,decision_at:'2026-09-08T10:00:00Z'},{...data,price_date:null}]) assert.equal(fresh(d,Date.parse('2026-09-07T11:00:00Z')),false);
});
test('sell needs an entered holding; zero target alone is not a sell',()=>{
  assert.equal(plan({...asset,target_weight:0},data,100,{},true).action,'skip');
  const p=plan({...asset,target_weight:0},data,100,{amount:25},true);
  assert.equal(p.action,'sell'); assert.equal(p.delta,-25);
});
test('buy sizes the difference, not the whole target',()=>{
  const p=plan(asset,data,100,{amount:20},true); assert.equal(p.action,'buy'); assert.equal(p.delta,5);
});
test('stale or invalid portfolio disables suggestions',()=>{
  assert.equal(plan(asset,data,100,{},false).action,'wait');
  assert.equal(plan(asset,data,100,{},true,false).action,'wait');
  assert.equal(plan({...asset,reference_price_usd:null},data,100,{},true).action,'wait');
});
test('small targets do not trigger uneconomic entries',()=>{
  assert.equal(plan({...asset,target_weight:.1},data,100,{},true).action,'skip');
  assert.equal(plan({...asset,target_weight:.1},data,100,{amount:25},true).action,'hold');
});
test('exit on stop requires known entry and position',()=>{
  const p=plan({...asset,reference_price_usd:95},data,100,{amount:25,entry:100},true);
  assert.equal(p.action,'sell'); assert.equal(p.target,0);
  assert.equal(plan({...asset,reference_price_usd:95},data,100,{},true).action,'buy');
});
