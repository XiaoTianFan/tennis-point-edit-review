import { $, el } from './model.js';
import { getLocale } from './i18n.js';

const labels = {
  zh: {title:'事件证据复核', boundary:'候选仅供取证；本页判断不直接写入逐分、技术统计或用户批准。', pending:'待核', confirmed:'事件已核实', rejected:'排除候选', uncertain:'仍不确定', racket_contact:'触拍', bounce:'落地', serve_onset:'发球起始', dead_ball:'首次死球', other:'其他', near:'近端', far:'远端', unknown:'未定', verdict:'判断', kind:'事件类型', side:'场端', frame:'复核帧', note:'观察说明', evidence:'原生证据引用（每行一项）', save:'保存事件复核', proposed:'候选', saved:'已记录', jump:'定位', duration:'秒', invalid:'请检查复核帧及必填项'},
  en: {title:'Event evidence review', boundary:'Evidence candidates only. These records do not adopt point scores, statistics or owner approvals.', pending:'Pending', confirmed:'Event verified', rejected:'Reject candidate', uncertain:'Uncertain', racket_contact:'Racket contact', bounce:'Bounce', serve_onset:'Serve onset', dead_ball:'First dead ball', other:'Other', near:'Near', far:'Far', unknown:'Unknown', verdict:'Verdict', kind:'Event type', side:'Court side', frame:'Reviewed frame', note:'Observation', evidence:'Native evidence references (one per line)', save:'Save event review', proposed:'Proposed', saved:'Recorded', jump:'Locate', duration:'s', invalid:'Check the reviewed frame and required fields'},
};
const seconds = value => { const [a,b=1]=String(value).split('/').map(Number); return a/b; };

export class VisionReview {
  constructor(select, save) {
    this.select=select; this.save=save; this.nodes=new Map(); this.elapsed=new Map(); this.drafts=new Map();
    document.addEventListener('visibilitychange',()=>{
      this.tick(); this.started=this.active && !document.hidden ? performance.now() : null;
    });
  }
  words() { return labels[getLocale() === 'zh' ? 'zh' : 'en']; }
  tick() { if (this.started != null && this.active) this.elapsed.set(this.active,(this.elapsed.get(this.active) ?? 0)+(performance.now()-this.started)/1000); this.started=null; }
  setProject(p) {
    this.p=p; const key=JSON.stringify([p.visionReview.events,getLocale()]);
    if (key!==this.key) { this.key=key; this.build(); }
    this.sync();
  }
  choose(event) {
    this.tick(); this.active=event.id; this.started=document.hidden ? null : performance.now();
    for (const [id,node] of this.nodes) node.card.classList.toggle('selected',id===event.id);
    this.select(event);
  }
  build() {
    const w=this.words(); this.nodes.clear(); $('review-list').replaceChildren(el('p',w.boundary,{class:'point-reason'}));
    $('review-panel').setAttribute('aria-label',w.title);
    for (const event of this.p.visionReview.events) {
      const card=el('article',null,{class:'point-card','data-event':event.id});
      const head=el('button',`${event.id} · ${seconds(event.seconds).toFixed(3)} ${w.duration}`,{class:'point-heading','aria-label':`${w.jump} ${event.id}`});
      head.onclick=()=>this.choose(event); const status=el('span','',{class:'row-status'});
      card.append(head,status,el('p',`${w.proposed}：${w[event.kind]} · ${w[event.side ?? 'unknown']}`,{class:'point-meta'}));
      if (event.intervalSeconds) card.append(el('p',event.intervalSeconds.map(x=>seconds(x).toFixed(3)).join(' – ')+` ${w.duration}`,{class:'point-reason'}));
      const form=el('form'), controls={};
      for (const [field,choices] of [['verdict',['pending','confirmed','rejected','uncertain']],['kind',['racket_contact','bounce','serve_onset','dead_ball','other']],['side',['unknown','near','far']]]) {
        const label=el('label',w[field],{class:'vision-field'}),input=el('select',null,{'aria-label':`${event.id} ${w[field]}`});
        for (const choice of choices) input.append(el('option',w[choice],{value:choice}));
        label.append(input); form.append(label); controls[field]=input;
      }
      const frameLabel=el('label',w.frame,{class:'vision-field'}),frame=el('input',null,{type:'number',min:0,max:this.p.assets.find(a=>a.id===this.p.visionReview.assetId).frames-1,step:1,required:'', 'aria-label':`${event.id} ${w.frame}`});
      frameLabel.append(frame);form.append(frameLabel);controls.frame=frame;
      for (const field of ['note','evidence']) {
        const label=el('label',w[field],{class:'vision-field'}),input=el('textarea',null,{rows:2,'aria-label':`${event.id} ${w[field]}`});
        label.append(input);form.append(label);controls[field]=input;
      }
      const values=()=>Object.fromEntries(Object.entries(controls).map(([key,input])=>[key,input.value]));
      form.oninput=()=>this.drafts.set(event.id,values());
      form.onchange=()=>this.drafts.set(event.id,values());
      const submit=el('button',w.save,{type:'submit'});form.append(submit);
      form.onsubmit=async e=>{
        e.preventDefault(); if (!form.reportValidity()) return;
        this.tick(); const previous=this.p.visionAnnotations?.[event.id],elapsed=this.elapsed.get(event.id),submitted=JSON.stringify(values());
        const reviewed={verdict:controls.verdict.value,kind:controls.kind.value,side:controls.side.value,frame:Number(controls.frame.value),note:controls.note.value,evidence:controls.evidence.value.split('\n').map(x=>x.trim()).filter(Boolean),reviewSeconds:elapsed != null ? (previous?.reviewSeconds ?? 0)+elapsed : previous?.reviewSeconds ?? null};
        submit.disabled=true;
        try {
          await this.save({type:'vision-review',eventId:event.id,annotation:reviewed}); this.elapsed.delete(event.id);
          if(JSON.stringify(values())===submitted)this.drafts.delete(event.id);
          this.sync();
        }
        catch { /* The shared save queue displays the failure and preserves its recovery draft. */ }
        submit.disabled=false;
        this.started=this.active && !document.hidden ? performance.now() : null;
      };
      card.append(form);this.nodes.set(event.id,{card,status,controls});$('review-list').append(card);
    }
  }
  sync() {
    const w=this.words();let recorded=0;
    for (const event of this.p.visionReview.events) {
      const value=this.p.visionAnnotations?.[event.id],node=this.nodes.get(event.id);
      const saved={verdict:'pending',kind:event.kind,side:event.side ?? 'unknown',frame:event.frame,note:'',evidence:[],...value};
      node.status.textContent=w[saved.verdict]; if(saved.verdict!=='pending')recorded++;
      const current={...saved,evidence:saved.evidence.join('\n'),...this.drafts.get(event.id)};
      for (const [key,input] of Object.entries(node.controls)) if(document.activeElement!==input) input.value=current[key] ?? '';
      node.card.classList.toggle('selected',event.id===this.active);
    }
    $('review-progress').textContent=`${w.saved} ${recorded} / ${this.p.visionReview.events.length}`;this.search();
  }
  localize() { if(this.p) { this.key=null; this.setProject(this.p); } }
  search() {
    const q=$('search').value.trim().toLowerCase();let count=0;
    for(const event of this.p.visionReview.events) {
      const found=!!q && [event.id,event.kind,event.side,this.p.visionAnnotations?.[event.id]?.note].join(' ').toLowerCase().includes(q);
      this.nodes.get(event.id).card.classList.toggle('search-match',found);if(found)count++;
    }
    $('search-count').textContent=q ? String(count) : '';
  }
}
