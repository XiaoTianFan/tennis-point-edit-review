const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const vm=require('node:vm');
const {call}=require('../skills/tennis-point-edit-review/scripts/premiere_mcp.cjs');
const {build}=require('../skills/tennis-point-edit-review/scripts/make_mogrt.cjs');
const {prepare}=require('../skills/tennis-point-edit-review/scripts/render_overlays.cjs');
const mf=require('../skills/tennis-point-edit-review/examples/ui-manifest.json');
const canvas={width:1920,height:1080};

test('English adapters localize all defaults and retain explicit names and language overrides',()=>{
  for(const component of Object.keys(mf.components)) {
    const en=prepare({id:component,component},mf,canvas,undefined,'en');
    assert.doesNotMatch(JSON.stringify(en.props),/[\u3400-\u9fff]/);
    assert.match(en.html,/<html lang="en">/);
    assert.equal(en.sourceSha256,mf.components[component].sha256);
  }
  const explicit=prepare({id:'override',component:'scoreboard',outputLanguage:'zh-CN',props:{nameA:'Custom Name'}},mf,canvas,undefined,'en');
  assert.equal(explicit.props.nameA,'Custom Name');assert.equal(explicit.props.gamesLabel,'局');
  const native=build('synthetic-output','Arial','en');
  assert.equal(native.manifest.outputLanguage,'en');
  assert.equal(native.manifest.components.serveLabel.props.label,'1st serve');
  assert.throws(()=>prepare({id:'bad',component:'scoreboard'},mf,canvas,undefined,'fr'),/Unsupported/);
});

async function server(mode,run) {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'tennis-mcp-test-'));
  const filename=path.join(dir,'server.cjs'),log=path.join(dir,'calls.txt');
  fs.writeFileSync(filename,`const fs=require('fs');require('readline').createInterface({input:process.stdin}).on('line',line=>{
    const m=JSON.parse(line);if(m.id===undefined)return;
    if(m.method==='initialize'){console.log(JSON.stringify({jsonrpc:'2.0',id:m.id,result:{serverInfo:{name:'fixture',version:'1'},capabilities:{},protocolVersion:'2025-03-26'}}));return;}
    fs.appendFileSync(${JSON.stringify(log)},m.method+'\\n');
    if(${JSON.stringify(mode)}==='timeout')return;
    if(${JSON.stringify(mode)}==='malformed'){console.log('not json');return;}
    const result=${JSON.stringify(mode)}==='error'?{isError:true,content:[{type:'text',text:'rejected'}]}:{content:[{type:'text',text:'{"success":false,"error":"host rejected"}'}]};
    console.log(JSON.stringify({jsonrpc:'2.0',id:m.id,result}));
  });`);
  try {await run({command:process.execPath,args:[filename],timeoutMs:500},log);}finally{
    const resolved=path.resolve(dir),tempRoot=path.resolve(os.tmpdir())+path.sep;
    if(!resolved.startsWith(tempRoot)||!path.basename(resolved).startsWith('tennis-mcp-test-'))throw new Error('Unsafe test cleanup path');
    fs.rmSync(resolved,{recursive:true,force:true});
  }
}
test('MCP rejects tool and nested host errors',async()=>{
  for(const mode of ['error','nested'])await server(mode,async(config)=>{
    const result=await call(config,{name:'fixture'});assert.equal(result.outcome,'tool_error');
  });
});
test('MCP timeout does not retry a possibly completed mutation',async()=>{
  await server('timeout',async(config,log)=>{
    const result=await call(config,{name:'insert_fixture'});
    assert.equal(result.outcome,'unknown');assert.match(result.error,/inspect host/);
    assert.equal(fs.readFileSync(log,'utf8'),'tools/call\n');
  });
});
test('MCP invalid stdout is not mistaken for success',async()=>{
  await server('malformed',async(config)=>{assert.equal((await call(config,{name:'fixture'})).outcome,'unknown');});
});
test('renderer uses canonical props and preserves navy panel with alpha canvas',()=>{
  const result=prepare({id:'synthetic',component:'serveLabel',props:{label:'二发 · 双误'}},mf,canvas);
  assert.match(result.html,/background:transparent/);assert.match(result.html,/#0A1B2B/);
  assert.equal(result.props.label,'二发 · 双误');
  assert.throws(()=>prepare({id:'../bad',component:'serveLabel'},mf,canvas));
  assert.throws(()=>prepare({id:'bad',component:'serveLabel',props:{unknown:3}},mf,canvas));
});
test('statistics preserve the canonical fade and reject invalid frames',()=>{
  const result=prepare({id:'panel',component:'statsPanel'},mf,canvas);
  assert.deepEqual(result.fade,{frames:[0,9,231,239],values:[0,1,1,0]});
  assert.equal(result.frame,9);
  assert.throws(()=>prepare({id:'bad',component:'statsPanel',props:{panelFrames:2}},mf,canvas));
});
test('local fit layout adapts reference graphics without changing default Premiere geometry',()=>{
  const entry={id:'label',component:'serveLabel'}, portrait={width:1080,height:1920};
  assert.throws(()=>prepare(entry,mf,portrait),/layout adapter/);
  const result=prepare(entry,mf,portrait,'fit');
  assert.match(result.html,/transform:scale\(0\.5625,0\.5625\)/);
  const original=prepare(entry,mf,canvas), fitted=prepare(entry,mf,canvas,'fit');
  assert.equal(original.html,fitted.html);
});
test('AE authoring source is parseable and honestly provisional',()=>{
  const result=build(path.join(os.tmpdir(),'synthetic-native'));
  assert.doesNotThrow(()=>new vm.Script(result.source));
  assert.equal(Object.keys(result.manifest.components).length,5);
  assert.match(result.manifest.qualification,/authoring_script_only/);
  assert.ok(result.manifest.propertyMap.scoreboard.includes('serverBOpacity'));
});
