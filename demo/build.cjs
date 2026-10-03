// Render the canonical components themselves; no parallel mock UI implementation.
const fs = require('node:fs');
const path = require('node:path');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const {transformSync} = require('esbuild');
const root = path.resolve(__dirname, '..');
const pkg = path.join(root, 'skills/tennis-point-edit-review');
const manifest = JSON.parse(fs.readFileSync(path.join(pkg, 'examples/ui-manifest.json'), 'utf8'));
const data = JSON.parse(fs.readFileSync(path.join(__dirname, 'mock-data.json'), 'utf8'));
const out = path.join(root, 'output/playwright');
fs.mkdirSync(out, {recursive:true});
const escape = s => String(s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function interpolate(v, xs, ys) {
  if(v<=xs[0]) return ys[0];
  for(let i=1;i<xs.length;i++) if(v<=xs[i]) return ys[i-1]+(ys[i]-ys[i-1])*(v-xs[i-1])/(xs[i]-xs[i-1]);
  return ys.at(-1);
}
function component(name, props={}, placement) {
  const def=manifest.components[name];
  const defaults=Object.fromEntries(def.properties.map(p=>[p.key,p.defaultValue]));
  const code=transformSync(fs.readFileSync(path.join(pkg,def.codeFile),'utf8'),{loader:'jsx',jsx:'transform'}).code;
  const Component=new Function('React','useCurrentFrame','interpolate',code+';return Component;')(React,()=>30,interpolate);
  const p=placement||def.placement1080p;
  const naturalHeight=p.naturalHeight||def.naturalSize.height;
  const html=renderToStaticMarkup(React.createElement(Component,{item:{props:{...defaults,font:'Microsoft YaHei, Noto Sans SC, sans-serif',...props}}}));
  return `<div data-component="${name}" style="position:absolute;left:${p.left}px;top:${p.top}px;width:${def.naturalSize.width}px;height:${naturalHeight}px;transform-origin:top left;transform:scale(${p.width/def.naturalSize.width},${p.height/naturalHeight})">${html}</div>`;
}
// Original schematic artwork. No real court, player, brand or source footage.
const court=`<svg viewBox="0 0 1920 1080" aria-label="Fictional court illustration" style="position:absolute;inset:0;width:100%;height:100%"><defs><linearGradient id="bg" x2="0" y2="1"><stop stop-color="#153d41"/><stop offset="1" stop-color="#0c242c"/></linearGradient></defs><rect width="1920" height="1080" fill="url(#bg)"/><g fill="none" stroke="#9eb8ae" stroke-width="3" opacity=".28"><path d="M720 245H1200L1580 940H340Z"/><path d="M755 245L430 940M1165 245L1490 940M608 470H1312M505 650H1415M960 470V650M528 607H1392"/><path d="M470 607H1450" stroke-width="6"/></g><text x="960" y="205" fill="#b7cfc6" opacity=".52" text-anchor="middle" font-size="23" letter-spacing="8" font-family="sans-serif">TENNIS MATCH EDIT</text><text x="960" y="1006" fill="#b7cfc6" text-anchor="middle" font-size="17" letter-spacing="3" font-family="sans-serif">FICTIONAL PLAYERS · SYNTHETIC DATA · TEMPLATE PREVIEW</text></svg>`;
function artboard(id,title,markup) {
  return `<section><h2>${escape(title)}</h2><div class="capture" id="${id}"><div class="canvas">${court}${markup}</div></div></section>`;
}
// A selected in-match instant consistent with the six-game mock score chain.
const score=data.previewScore;
let boards=artboard('scoreboard','Scoreboard, post-contact serve speed and optional note',
  component('scoreboard',{nameA:'Player A',nameB:'Player B',gamesA:String(score.before.games.A),gamesB:String(score.before.games.B),pointsA:score.before.display.A,pointsB:score.before.display.B,server:score.server,rule:'NO-AD · '+score.pointId})+
  component('serveLabel',{label:'一发'})+
  component('serveSpeed',{speed:String(data.serveEstimates.find(s=>s.pointId==='DEMO034').launchSpeedKphEstimate)})+
  component('explanation',{title:'演示说明',detail:'虚构选手与数据；本图展示计分板、发球标签及可选补充说明。'}));
const ids=['stats-overview','stats-serve','stats-return','stats-rally','stats-court'];
for(const [index,p] of data.panels.entries()) {
  // Same JSX, data-aware canvas height: keep all rows and their sublabels clear.
  // This adapts the preview container, not the stored template or live timeline.
  const rowHeight=p.rows.reduce((sum,r)=>sum+Math.max(p.rows.length>8?50:64,(r.asub||r.bsub?75:r.sub?72:47)),0);
  const naturalHeight=Math.max(900,Math.ceil(rowHeight+374));
  const scale=Math.min(.9,864/naturalHeight),w=1600*scale,h=naturalHeight*scale;
  boards+=artboard(ids[index],`${index+1} / 5 — ${p.eyebrow}`,component('statsPanel',{
    title:p.title,eyebrow:p.eyebrow,pageNumber:`${index+1} / 5`,nameA:'Player A',nameB:'Player B',
    subtitle:'虚构短盘演示 · Player A 4 : 2 Player B',rows:JSON.stringify(p.rows),
    footnote:'',footnote2:'',disclaimer:'演示数据 · 非真实比赛统计'
  },{left:(1920-w)/2,top:(1080-h)/2,width:w,height:h,naturalHeight}));
}
boards+=artboard('review','Stable review identifiers and persistent game / server context',
  component('reviewId',{reviewId:'R002',pointId:'P014'})+
  component('reviewLabel',{phaseLabel:'第3局',serverName:'Player A',serveLabel:'二发'})+
  component('explanation',{title:'补充观察',detail:'临时补充信息放在左下角；编号与局次保持在固定位置。'},{left:48,top:866,width:784,height:105.6}));
const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Tennis Match Edit — Synthetic Template Gallery</title><style>body{margin:0;background:#07131f;color:#f5f7fa;font-family:system-ui,sans-serif}main{width:1280px;margin:48px auto}h1{font-size:32px;margin:0}p{color:#a8b9c7;margin:12px 0 36px}h2{font-size:17px;font-weight:500;color:#dae4ee;margin:32px 0 14px}.capture{width:1280px;height:720px;position:relative;overflow:hidden}.canvas{position:absolute;width:1920px;height:1080px;transform:scale(.6666666667);transform-origin:top left}</style></head><body><main><h1>Tennis Match Edit</h1><p>Actual navy/lime JSX components · fictional event data · reproducible still previews</p>${boards}</main></body></html>`;
fs.writeFileSync(path.join(out,'gallery.html'),html);
console.log('Built seven previews from the seven canonical JSX components.');
