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

test('human-reviewed badges distinguish count and detail gaps without resolving them', async () => {
  const m=await model, r={...row,countingIssueRequired:true};
  const x={...m.blank(),scoringPlayerId:'B',deadBallType:'out',reviewConfirmed:true};
  assert.equal(m.reviewStatus(r,x),'partial');
  assert.equal(m.reviewBadge(r,x),'reviewedCounting');
  assert.equal(m.reviewBadge(r,{...x,countingIssueResolved:true}),'status.resolved');
  assert.equal(m.reviewBadge(row,{...x,deadBallType:null}),'reviewedIncomplete');
  assert.equal(m.reviewBadge(r,{...x,reviewConfirmed:false}),'status.partial');
  assert.equal(m.reviewBadge(r,{...x,winnerUndetermined:true,scoringPlayerId:null}),'status.unresolved');
});

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

test('manual first labeling never infers a serving side; explicit edits survive', async () => {
  const m=await model;
  const p={...project,review:{purpose:'initial-labeling'}};
  const r={...row,serverId:null};
  let x=m.answer(p,r);
  assert.equal(x.serverId,null);
  assert.equal(m.reviewStatus(r,x),'pending');
  assert.throws(()=>m.changeAnswer(p,r,x,'doubleFaultConfirmed',true));
  assert.throws(()=>m.changeAnswer(p,r,x,'deadBallType','ace'));
  x=m.changeAnswer(p,r,x,'serverId','B');
  x=m.changeAnswer(p,r,x,'deadBallType','ace');
  assert.equal(x.scoringPlayerId,'B');
  x=m.changeAnswer(p,r,x,'serverId','A');
  assert.equal(x.scoringPlayerId,null);
  assert.equal(x.deadBallType,null);
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

test('export summary uses the actual project dimensions, rational fps and hold duration', async () => {
  const m=await model;
  const p={width:1920,height:1080,fps:'30000/1001',needsRebuild:['presentation-order'],clips:[
    {inFrame:50,outFrame:80},{kind:'hold',inFrame:79,durationFrames:15}
  ]};
  const before=JSON.stringify(p), summary=m.exportSummary(p);
  assert.equal(summary.frames,45);
  assert.equal(summary.fps,'30000/1001');
  assert.equal(summary.width,1920); assert.equal(summary.height,1080);
  assert.ok(Math.abs(summary.seconds-1.5015)<1e-9);
  assert.deepEqual(summary.reasons,['presentation-order']);
  summary.reasons.push('graphics-timing');
  assert.equal(JSON.stringify(p),before);
  const converted=m.exportSummary(p,{width:1280,height:720,fps:'60'});
  assert.equal(converted.frames,90);
  assert.equal(converted.width,1280);
  assert.ok(Math.abs(converted.seconds-summary.seconds)<=.5/60);
  assert.equal(JSON.stringify(p),before);
});

test('review is a reversible layout of the same clips, not copied cuts or answer changes', async () => {
  const m=await model;
  const p={...project,review:{rows:[{pointId:'P2'}]},overlays:[{id:'score'},{id:'r',view:'review'},{id:'s',view:'full'}],clips:[{id:'a',pointId:'P1',inFrame:0,outFrame:20},{id:'b',pointId:'P2',inFrame:20,outFrame:40},{id:'c',pointId:'P2',inFrame:40,outFrame:60},{id:'d',pointId:'P3',inFrame:60,outFrame:100}]};
  const original=JSON.stringify(p);
  assert.deepEqual(m.layout(p,'review').map(c=>[c.id,c.startFrame,c.endFrame]),[['b',0,20],['c',20,40]]);
  assert.equal(m.layout(p,'full').at(-1).endFrame,100);
  assert.equal(JSON.stringify(p),original);
  assert.deepEqual(m.viewOverlays(p,'review').map(o=>o.id),['score','r']);
  assert.deepEqual(m.viewOverlays(p,'full').map(o=>o.id),['score','s']);
});
test('trim cursor snap uses screen distance at multiple zoom levels; shift bypass and distant edges',async()=>{
  const m=await model;
  for(const px of [.25,1,8]) {
    const near=100+Math.floor(7/px);
    assert.deepEqual(m.snapEdge(near-50,50,100,px),{delta:50,snapped:true});
    assert.equal(m.snapEdge(60,50,100,px,true).snapped,false);
    assert.equal(m.snapEdge(Math.ceil(9/px),100,100,px).snapped,false);
  }
});
test('export remains locked until both current approvals and complete statistics exist',async()=>{
 const m=await model,p={...project,review:{ledgerRevision:'v2'},needsRebuild:[]};
 assert.equal(m.exportBlockers(p),true);
 p.approval={ledgerRevision:'v2',pointAttribution:true,statistics:true};
 assert.equal(m.exportBlockers(p),true);
 p.statistics={ledgerRevision:'v2',status:'complete'};assert.equal(m.exportBlockers(p),false);
 p.needsRebuild=['score'];assert.equal(m.exportBlockers(p),true);
});

test('cursor point changes reveal only the review scroller; playback and answers preserve scroll', async()=>{
 const encode=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
 const source=fs.readFileSync(path.join(root,'scripts/local_web/review.js'),'utf8')
  .replace('./model.js',encode(fs.readFileSync(path.join(root,'scripts/local_web/model.js'),'utf8')))
  .replace('./i18n.js',encode(fs.readFileSync(path.join(root,'scripts/local_web/i18n.js'),'utf8')));
 const {Review}=await import(encode(source));
 const list={scrollTop:0,getBoundingClientRect:()=>({top:100,bottom:600})};
 const selected=new Set();
 const card=(pid,top)=>({classList:{toggle:(name,on)=>on?selected.add(pid):selected.delete(pid)},getBoundingClientRect:()=>({top:top-list.scrollTop,bottom:top+350-list.scrollTop})});
 const view=Object.assign(Object.create(Review.prototype),{nodes:new Map([['P1',{card:card('P1',108)}],['P2',{card:card('P2',900)}]])});
 const previous=global.document;global.document={getElementById:id=>{assert.equal(id,'review-list');return list;}};
 try {
  view.highlight('P1',{reveal:true});assert.equal(list.scrollTop,0);
  view.highlight('P2',{reveal:true});assert.equal(list.scrollTop,792);assert.deepEqual([...selected],['P2']);
  list.scrollTop=42;view.highlight('P2',{reveal:true});assert.equal(list.scrollTop,42);
  view.highlight('P1');assert.equal(list.scrollTop,42);
  view.highlight('unlisted',{reveal:true});assert.equal(list.scrollTop,42);assert.equal(selected.size,0);
  view.highlight('P2',{reveal:true});assert.equal(list.scrollTop,792);
 } finally {global.document=previous;}
});
