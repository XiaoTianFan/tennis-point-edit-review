// Render canonical React JSX to full-canvas RGBA PNGs; never operate an editor.
// Requires react, react-dom, esbuild, playwright in Node's module search path.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const {transformSync}=require('esbuild');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
function interpolate(v,xs,ys) {
  if(v<=xs[0])return ys[0];
  for(let i=1;i<xs.length;i++)if(v<=xs[i])return ys[i-1]+(ys[i]-ys[i-1])*(v-xs[i-1])/(xs[i]-xs[i-1]);
  return ys.at(-1);
}
function prepare(entry,manifest,canvas,layout) {
  if(!/^[A-Za-z0-9_-]+$/.test(entry.id))throw new Error('Use a safe unique overlay id');
  const def=manifest.components[entry.component]; if(!def)throw new Error('Unknown component');
  const source=fs.readFileSync(path.join(root,def.codeFile),'utf8').replace(/\r\n/g,'\n');
  if(hash(source)!==def.sha256)throw new Error('Canonical template hash mismatch');
  const props=Object.fromEntries(def.properties.map(p=>[p.key,p.defaultValue]));
  for(const [key,value] of Object.entries(entry.props||{})) {
    const property=def.properties.find(p=>p.key===key);
    if(!property)throw new Error('Unknown property: '+key);
    const type=property.type==='number'?'number':property.type==='boolean'?'boolean':'string';
    if(typeof value!==type || (type==='number'&&!Number.isFinite(value)))throw new Error('Invalid property: '+key);
    props[key]=value;
  }
  let h=entry.naturalHeight??def.naturalSize.height;
  let placement={...def.placement1080p,...entry.placement};
  if(entry.component==='statsPanel') {
    const rows=JSON.parse(props.rows);
    if(!Array.isArray(rows)||rows.length>11)throw new Error('Statistics need an array of <= 11 rows');
    if(!Number.isInteger(props.panelFrames)||props.panelFrames<20)throw new Error('Invalid panel duration');
    if(!entry.naturalHeight) {
      const rowHeight=rows.reduce((sum,r)=>sum+Math.max(rows.length>8?50:64,(r.asub||r.bsub?75:r.sub?72:47)),0);
      h=Math.max(900,Math.ceil(rowHeight+374));
      if(!entry.placement) {const s=Math.min(.9,864/h);placement={left:(1920-1600*s)/2,top:(1080-h*s)/2,width:1600*s,height:h*s};}
    }
  }
  if(!Number.isFinite(h)||h<=0)throw new Error('Invalid naturalHeight');
  for(const key of ['left','top','width','height'])if(!Number.isFinite(placement[key])||placement[key]<0)throw new Error('Invalid placement');
  if(!placement.width||!placement.height)throw new Error('Zero-sized overlay');
  // Placement is specified in the canonical 1080p reference canvas.
  if(canvas.width*1080!==canvas.height*1920 && layout!=='fit')throw new Error('Non-16:9 needs an explicit layout adapter');
  const scale=Math.min(canvas.width/1920,canvas.height/1080);
  const offsetX=(canvas.width-1920*scale)/2,offsetY=(canvas.height-1080*scale)/2;
  const frame=entry.frame??(entry.component==='statsPanel'?9:0);
  if(!Number.isInteger(frame)||frame<0)throw new Error('Frame must be a nonnegative integer');
  const code=transformSync(source,{loader:'jsx',jsx:'transform'}).code;
  const Component=new Function('React','useCurrentFrame','interpolate',code+';return Component;')(React,()=>frame,interpolate);
  const markup=renderToStaticMarkup(React.createElement(Component,{item:{props}}));
  const style=`position:absolute;left:${offsetX+placement.left*scale}px;top:${offsetY+placement.top*scale}px;width:${def.naturalSize.width}px;height:${h}px;transform-origin:top left;transform:scale(${placement.width/def.naturalSize.width*scale},${placement.height/h*scale})`;
  return {html:`<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:transparent;width:100%;height:100%;overflow:hidden}*{animation:none!important}</style></head><body><div id="overlay" style="${style}">${markup}</div></body></html>`,props,placement,naturalHeight:h,frame,
    sourceSha256:def.sha256,fade:entry.component==='statsPanel'?{frames:[0,9,props.panelFrames-9,props.panelFrames-1],values:[0,1,1,0]}:null};
}
async function render(request,outDir) {
  const manifest=read(path.join(root,'examples/ui-manifest.json'));
  const canvas=request.canvas||{width:1920,height:1080};
  for(const key of ['width','height'])if(!Number.isInteger(canvas[key])||canvas[key]<1||canvas[key]>8192)throw new Error('Invalid canvas');
  const ids=new Set();
  const prepared=request.entries.map(entry=>{
    if(ids.has(entry.id))throw new Error('Duplicate overlay id');ids.add(entry.id);
    return {entry,data:prepare(entry,manifest,canvas,request.layout)};
  });
  if(fs.existsSync(outDir))throw new Error('Use a new output directory to preserve render evidence');
  fs.mkdirSync(outDir,{recursive:true});
  const browser=await chromium.launch({headless:true,...(request.browserChannel?{channel:request.browserChannel}:{})});
  const results=[];
  try {
    const page=await browser.newPage({viewport:canvas,deviceScaleFactor:1});
    await page.route('**/*',route=>route.abort()); // No external fonts, assets or network.
    for(const {entry,data} of prepared) {
      await page.setContent(data.html);await page.evaluate(()=>document.fonts.ready);
      const overflow=await page.evaluate(()=>[...document.querySelectorAll('#overlay *')].filter(e=>{
        const s=getComputedStyle(e);return s.opacity!=='0' && (e.scrollWidth>e.clientWidth+2 || e.scrollHeight>e.clientHeight+2);
      }).map(e=>({text:e.textContent.slice(0,160),width:e.clientWidth,scrollWidth:e.scrollWidth,height:e.clientHeight,scrollHeight:e.scrollHeight})));
      const filename=entry.id+'.png';
      await page.screenshot({path:path.join(outDir,filename),omitBackground:true});
      results.push({id:entry.id,component:entry.component,file:filename,canvas,...data,html:undefined,
        pngSha256:hash(fs.readFileSync(path.join(outDir,filename))),overflow,
        editability:'regenerate_from_props; PNG text is not editable in Premiere'});
    }
  } finally {await browser.close();}
  const result={schema:'tennis-overlay-render/v1',templateVersion:manifest.version,canvas,entries:results,
    qualification:'rendered_only; verify target composition, alpha, color, scale and timing'};
  fs.writeFileSync(path.join(outDir,'render-manifest.json'),JSON.stringify(result,null,2));
  return result;
}
module.exports={prepare,render};
if(require.main===module) (async()=>{
  const [requestPath,outDir]=process.argv.slice(2);
  if(!outDir)throw new Error('Usage: node render_overlays.cjs request.json new-output-directory');
  const result=await render(read(requestPath),outDir);
  console.log(JSON.stringify({rendered:result.entries.length,overflow:result.entries.filter(e=>e.overflow.length).map(e=>e.id),outDir}));
})().catch(error=>{console.error(error.message);process.exitCode=1;});
