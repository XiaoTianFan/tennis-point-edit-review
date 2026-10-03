// CLI-first Playwright capture, using an isolated browser session and loopback HTTP.
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const {execFile}=require('node:child_process');
const {promisify}=require('node:util');
const run=promisify(execFile);
const root=path.resolve(__dirname,'..');
const cli=path.join(root,'node_modules/@playwright/cli/playwright-cli.js');
const output=path.join(root,'output/playwright');
const session='tennis-repo-'+process.pid;
const node=process.env.PLAYWRIGHT_NODE_PATH||process.env.npm_node_execpath||process.execPath;
async function command(...args){
  const result=await run(node,[cli,'-s='+session,...args],{cwd:root,windowsHide:true,maxBuffer:2*1024*1024});
  if(/### Error/.test(result.stdout))throw new Error(result.stdout);
  return result.stdout;
}
async function main(){
  const html=fs.readFileSync(path.join(output,'gallery.html'));
  const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(html);});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{
    await command('open',`http://127.0.0.1:${server.address().port}/`);
    await command('resize','1440','1000');
    await command('snapshot');
    const checked=await command('run-code','--filename','demo/browser-checks.js');
    fs.writeFileSync(path.join(output,'browser-checks.txt'),checked);
    console.log(checked.split('### Ran')[0].trim());
    const images=path.join(root,'docs/images');fs.mkdirSync(images,{recursive:true});
    for(const id of ['scoreboard','stats-overview','stats-serve','stats-return','stats-rally','stats-court','review']){
      await command('screenshot','#'+id,'--filename',`output/playwright/${id}.png`);
      fs.copyFileSync(path.join(output,id+'.png'),path.join(images,id+'.png'));
      console.log('Captured '+id+'.png');
    }
  }finally{
    try{await command('close');}finally{await new Promise(resolve=>server.close(resolve));}
  }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
