const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../skills/tennis-point-edit-review');
const model = import('data:text/javascript;base64,' + fs.readFileSync(path.join(root, 'scripts/local_web/model.js')).toString('base64'));
const project = { players: [{id:'A'}, {id:'B'}], fps:'30000/1001', answers:{} };
const row = { pointId:'P001', serverId:'A' };

test('unknown winner cannot retain ACE or double fault; returning to a side is explicit', async () => {
  const m = await model;
  let x = m.changeAnswer(project,row,{...m.blank(),scoringPlayerId:'A',deadBallType:'ace'},'scoringPlayerId','undetermined');
  assert.equal(x.scoringPlayerId,null); assert.equal(x.deadBallType,null);
  assert.equal(m.reviewStatus(row,x),'unresolved');
  x=m.changeAnswer(project,row,x,'doubleFaultConfirmed',true);
  assert.equal(x.scoringPlayerId,'B'); assert.equal(x.winnerUndetermined,false);
  x=m.changeAnswer(project,row,x,'deadBallType','ace');
  assert.equal(x.scoringPlayerId,'A'); assert.equal(x.doubleFaultConfirmed,null);
});
test('replay clears scoring implications; initial data never claims human review', async () => {
  const m=await model;
  const x=m.changeAnswer(project,row,{...m.blank(),scoringPlayerId:'B',doubleFaultConfirmed:true,extra:true},'deadBallType','replay');
  assert.equal(x.scoringPlayerId,null); assert.equal(x.extra,false); assert.equal(m.reviewStatus(row,x),'replay');
  assert.equal(m.answer(project,{...row,initial:{reviewConfirmed:true}}).reviewConfirmed,false);
});
test('multiple clips per point retain independent offsets and half-open overlay bounds', async () => {
  const m=await model;
  const p={...project,clips:[{id:'c1',pointId:'P001',inFrame:10,outFrame:40},{id:'c2',pointId:'P001',inFrame:50,outFrame:65}]};
  assert.equal(m.rate(p),30000/1001);
  assert.deepEqual(m.layout(p).map(c=>[c.startFrame,c.endFrame]),[[0,30],[30,45]]);
  assert.deepEqual(m.bounds({anchor:'source',startFrame:5,endFrame:22},p.clips[0]),[0,12]);
});
test('packaged minimal plan uses declared canonical props', () => {
  const p=JSON.parse(fs.readFileSync(path.join(root,'examples/local-edit-plan.json')));
  const manifest=JSON.parse(fs.readFileSync(path.join(root,'examples/ui-manifest.json')));
  for(const o of p.overlays){
    const keys=manifest.components[o.component].properties.map(x=>x.key);
    for(const prop of Object.keys(o.props))assert.ok(keys.includes(prop),`${o.id}: ${prop}`);
  }
});
