// Terminal-only stdio MCP client. No desktop automation and no automatic retries.
// Usage: node premiere_mcp.cjs config.json request.json result.json
// config: {command, args:[], env:{}, timeoutMs:60000}; request: {name, arguments:{}}
const fs = require('node:fs');
const {spawn} = require('node:child_process');
const readline = require('node:readline');

async function call(config, request) {
  if (!config.command || !Array.isArray(config.args) || !request.name ||
      typeof request.name !== 'string' || /\0/.test(config.command)) throw new Error('Invalid config/request');
  const timeoutMs = config.timeoutMs ?? 60000;
  if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 600000) throw new Error('Invalid timeoutMs');
  const child = spawn(config.command, config.args, {shell:false, windowsHide:true,
    env:{...process.env, ...config.env}, stdio:['pipe','pipe','pipe']});
  const lines = readline.createInterface({input:child.stdout});
  let nextId=0, stderr='', sentTool=false;
  const pending = new Map();
  child.stderr.on('data', data => { stderr=(stderr+data.toString()).slice(-12000); });
  function fail(error) { for(const p of pending.values()) {clearTimeout(p.timer);p.reject(error);} pending.clear(); }
  child.on('error', fail);
  child.on('exit', (code, signal) => fail(new Error(`MCP server exited (${code ?? signal}); operation outcome may be unknown`)));
  child.stdin.on('error', fail);
  lines.on('line', line => {
    let message;
    try {message=JSON.parse(line);} catch {fail(new Error('Non-JSON server stdout; invalid stdio MCP framing'));return;}
    if (message.id !== undefined && (message.result !== undefined || message.error)) {
      const p=pending.get(message.id); if(!p)return;
      clearTimeout(p.timer);pending.delete(message.id);
      if(message.error)p.reject(new Error(JSON.stringify(message.error)));else p.resolve(message.result);
    } else if(message.method && message.id !== undefined) {
      // This client grants no sampling, elicitation or filesystem roots.
      child.stdin.write(JSON.stringify({jsonrpc:'2.0',id:message.id,error:{code:-32601,message:'Client capability not provided'}})+'\n');
    }
  });
  function rpc(method, params) {
    return new Promise((resolve,reject) => {
      const id=++nextId;
      const timer=setTimeout(()=>{pending.delete(id);reject(new Error(`Timed out during ${method}; inspect host before retrying any mutation`));},timeoutMs);
      pending.set(id,{resolve,reject,timer});
      child.stdin.write(JSON.stringify({jsonrpc:'2.0',id,method,params})+'\n');
    });
  }
  try {
    const initialized=await rpc('initialize',{protocolVersion:'2025-03-26',capabilities:{},
      clientInfo:{name:'tennis-terminal-client',version:'1.0.0'}});
    child.stdin.write(JSON.stringify({jsonrpc:'2.0',method:'notifications/initialized'})+'\n');
    sentTool=true;
    const result=await rpc('tools/call',{name:request.name,arguments:request.arguments||{}});
    const structured=result.structuredContent;
    let inner=structured;
    if(!inner) {try {inner=JSON.parse(result.content?.find(c=>c.type==='text')?.text);} catch {}}
    return {schema:'tennis-mcp-result/v1',server:initialized.serverInfo,request,
      outcome:result.isError || inner?.success===false ? 'tool_error' : 'returned',result,stderr};
  } catch(error) {
    return {schema:'tennis-mcp-result/v1',request,outcome:sentTool?'unknown':'connection_error',error:error.message,stderr};
  } finally {
    fail(new Error('Client closed'));lines.close();child.stdin.end();child.kill();
  }
}

module.exports={call};
if(require.main===module) (async()=>{
  const [configPath,requestPath,outputPath]=process.argv.slice(2);
  if(!outputPath)throw new Error('Usage: node premiere_mcp.cjs config.json request.json result.json');
  if(fs.existsSync(outputPath))throw new Error('Use a new result path; refusal to overwrite evidence');
  const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
  const result=await call(read(configPath),read(requestPath));
  fs.writeFileSync(outputPath,JSON.stringify(result,null,2));
  console.log(JSON.stringify({outcome:result.outcome,outputPath,error:result.error}));
  if(result.outcome!=='returned')process.exitCode=1;
})().catch(error=>{console.error(error.message);process.exitCode=1;});
