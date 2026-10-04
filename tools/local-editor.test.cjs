const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../skills/tennis-point-edit-review');
const model = import('data:text/javascript;base64,' + fs.readFileSync(path.join(root, 'scripts/local_web/model.js')).toString('base64'));
const loadUi = name => import('data:text/javascript;base64,' + fs.readFileSync(path.join(root, 'scripts/local_web', name)).toString('base64'));
const language = loadUi('i18n.js');
const geometry = loadUi('view-state.js');
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

test('English and Chinese cover UI keys and preserve substitution values', async () => {
  const i = await language;
  const placeholders = s => [...s.matchAll(/\{(\w+)\}/g)].map(m=>m[1]).sort();
  for (const [key, pair] of Object.entries(i.messages)) {
    assert.equal(pair.length, 2, key);
    assert.ok(pair.every(v=>typeof v==='string' && v.length), key);
    assert.deepEqual(placeholders(pair[0]), placeholders(pair[1]), key);
  }
  const html=fs.readFileSync(path.join(root,'scripts/local_web/index.html'),'utf8');
  for (const match of html.matchAll(/data-i18n(?:-[\w-]+)?="([^"]+)"/g)) assert.ok(i.messages[match[1]], match[1]);
  const m=await model;
  for (const [cause] of m.causes) assert.ok(i.messages['cause.'+cause]);
  for(const status of ['pending','partial','resolved','replay','unresolved']) assert.ok(i.messages['status.'+status]);
  for(const component of Object.keys(JSON.parse(fs.readFileSync(path.join(root,'examples/ui-manifest.json'))).components)) assert.ok(i.messages['component.'+component]);
  for(const file of ['app.js','review.js','player.js','timeline.js']) {
    const source=fs.readFileSync(path.join(root,'scripts/local_web',file),'utf8');
    for (const match of source.matchAll(/(?:\bt|\bnotice|\bsaveState)\(["']([^"']+)["']/g)) {
      if (!match[1].endsWith('.')) assert.ok(i.messages[match[1]], file+': '+match[1]);
    }
  }
  for(const locale of ['en','zh']) {
    i.setLocale(locale);
    const result=i.t('pointMeta',{set:1,game:2,server:'Player {literal} <A>',serve:'1 → 2'});
    assert.ok(result.includes('Player {literal} <A>'));
    assert.ok(result.includes('1 → 2'));
  }
  assert.match(i.t('wholeFrames'),/整数/);
  assert.match(i.errorText('Clip outside source or empty'),/至少保留一帧/);
  assert.match(i.errorText('decoder diagnostic 42'),/decoder diagnostic 42/);
  i.setLocale('unsupported'); assert.equal(i.getLocale(),'en');
});

test('cursor anchored zoom preserves the frame under the pointer and clamps extremes', async () => {
  const {zoomAt}=await geometry;
  const original={zoom:2,scroll:400,pointer:300};
  const next=zoomAt(original.zoom,-200,original.scroll,original.pointer);
  assert.ok(next.zoom>original.zoom);
  assert.ok(Math.abs((next.scroll+300)/next.zoom - (400+300)/2)<1e-9);
  const back=zoomAt(next.zoom,200,next.scroll,300);
  assert.ok(Math.abs(back.zoom-2)<1e-9); assert.ok(Math.abs(back.scroll-400)<1e-9);
  assert.equal(zoomAt(8,-10000,40,10).zoom,8);
  assert.equal(zoomAt(.5,10000,0,400).scroll,0);
  assert.equal(zoomAt(.5,10000,0,400).zoom,.5);
});

test('pane limits retain usable preview space and wheel units normalize across devices', async () => {
  const {paneLimits,clamp,wheelPixels}=await geometry;
  for(const [width,height] of [[1331,871],[1024,768],[780,640]]) {
    const limits=paneLimits(width,height);
    assert.ok(width-limits.review[1]>=426);
    assert.ok(height-limits.timeline[1]>=385);
    assert.equal(clamp(-1,...limits.review),250);
  }
  assert.equal(wheelPixels({deltaX:0,deltaY:3,deltaMode:1},900),48);
  assert.equal(wheelPixels({deltaX:0,deltaY:-1,deltaMode:2},900),-900);
  assert.equal(wheelPixels({deltaX:120,deltaY:0,deltaMode:0},900),120);
});
