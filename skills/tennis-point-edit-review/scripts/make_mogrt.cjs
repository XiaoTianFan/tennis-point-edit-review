// Build an AE authoring script, not an editor connection or a binary MOGRT.
// Execute the generated .jsx in a compatible After Effects host, then qualify in Pr.
// Usage: node make_mogrt.cjs new-output-directory [PostScript-font-name]
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
function build(outDir,font='MicrosoftYaHei') {
  const root=path.resolve(__dirname,'..');
  const mf=JSON.parse(fs.readFileSync(path.join(root,'examples/ui-manifest.json'),'utf8'));
  const components=['scoreboard','serveLabel','serveSpeed','reviewId','reviewLabel'];
  const specs=Object.fromEntries(components.map(name=>{
    const d=mf.components[name];
    const actual=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,d.codeFile),'utf8').replace(/\r\n/g,'\n')).digest('hex');
    if(actual!==d.sha256)throw new Error('Canonical source hash mismatch');
    return [name,{size:d.naturalSize,props:Object.fromEntries(d.properties.map(p=>[p.key,p.defaultValue])),sha256:d.sha256}];
  }));
  const config={outDir:path.resolve(outDir).replace(/\\/g,'/'),font,version:mf.version,specs};
  const literal=JSON.stringify(config).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
  const source=`// Generated native adapter. React JSX is not evaluated in After Effects.
(function () {
  var cfg=${literal};
  if (app.project && (app.project.numItems > 0 || app.project.file)) {
    throw new Error("Open an empty After Effects workspace first; existing projects are protected.");
  }
  var out=new Folder(cfg.outDir); if(!out.exists && !out.create())throw new Error("Cannot create output directory");
  var project=app.project || app.newProject();
  function color(hex) {return [parseInt(hex.substr(1,2),16)/255,parseInt(hex.substr(3,2),16)/255,parseInt(hex.substr(5,2),16)/255];}
  function expose(prop,comp,name) {
    if(!prop.canAddToMotionGraphicsTemplate(comp) || !prop.addToMotionGraphicsTemplateAs(comp,name))throw new Error("Cannot expose "+name);
  }
  function box(comp,name,x,y,w,h,fill) {
    var layer=comp.layers.addShape();layer.name=name;
    var group=layer.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
    var contents=group.property("ADBE Vectors Group");
    var rect=contents.addProperty("ADBE Vector Shape - Rect");rect.property("ADBE Vector Rect Size").setValue([w,h]);
    var paint=contents.addProperty("ADBE Vector Graphic - Fill");paint.property("ADBE Vector Fill Color").setValue(color(fill));
    layer.property("ADBE Transform Group").property("ADBE Position").setValue([x+w/2,y+h/2]);return layer;
  }
  function text(comp,key,value,x,y,w,h,size,fill,center) {
    var layer=comp.layers.addText(String(value));layer.name=key;
    var prop=layer.property("ADBE Text Properties").property("ADBE Text Document");
    var doc=prop.value;doc.font=cfg.font;doc.fontSize=size;doc.fauxBold=true;doc.fillColor=color(fill);doc.applyFill=true;doc.applyStroke=false;
    doc.justification=ParagraphJustification.LEFT_JUSTIFY;prop.setValue(doc);
    // Re-evaluate text bounds after edits so cells retain centering and vertical alignment.
    layer.property("ADBE Transform Group").property("ADBE Anchor Point").expression=
      "var r=sourceRectAtTime(time,false);[r.left"+(center?"+r.width/2":"")+",r.top+r.height/2]";
    layer.property("ADBE Transform Group").property("ADBE Position").setValue([x+(center?w/2:0),y+h/2]);
    expose(prop,comp,key);return layer;
  }
  var report=["Native adapter generation: "+cfg.version,"Host AE: "+app.version,"Font requested: "+cfg.font];
  for(var name in cfg.specs) {
    if(!cfg.specs.hasOwnProperty(name))continue;
    var spec=cfg.specs[name],p=spec.props,w=spec.size.width,h=spec.size.height;
    var comp=project.items.addComp("tennis-"+name,w,h,1,120,30);
    comp.motionGraphicsTemplateName="tennis-"+name;
    box(comp,"panel",0,0,w,h,p.panel);
    if(name!=="scoreboard")box(comp,"accent-edge",0,0,5,h,p.accent);
    if(name==="scoreboard") {
      box(comp,"header",0,0,440,28,p.header);
      box(comp,"games-cells",316,28,56,104,p.header);box(comp,"points-cells",372,28,68,104,p.accent);
      text(comp,"rule",p.rule,12,0,300,28,13,p.accent,false);
      text(comp,"gamesLabel",p.gamesLabel,316,0,56,28,13,p.ink,true);
      text(comp,"pointsLabel",p.pointsLabel,372,0,68,28,13,p.ink,true);
      var keys=["A","B"];
      for(var row=0;row<2;row++) {
        var k=keys[row],y=28+row*52;
        text(comp,"name"+k,p["name"+k],28,y,288,52,23,p.ink,false);
        text(comp,"games"+k,p["games"+k],316,y,56,52,28,p.ink,true);
        text(comp,"points"+k,p["points"+k],372,y,68,52,30,p.header,true);
        var dot=box(comp,"server"+k,11,y+23,6,6,p.accent);
        var dp=dot.property("ADBE Root Vectors Group").property(1).property("ADBE Vectors Group").property(1);
        dp.property("ADBE Vector Rect Roundness").setValue(3);
        var opacity=dot.property("ADBE Transform Group").property("ADBE Opacity");
        opacity.setValue(p.server===k?100:0);expose(opacity,comp,"server"+k+"Opacity");
      }
    } else if(name==="serveLabel") {
      text(comp,"label",p.label,12,0,w-24,h,27,p.ink,true);
    } else if(name==="serveSpeed") {
      text(comp,"qualifier",p.qualifier,12,0,38,h,15,p.ink,false);
      text(comp,"speed",p.speed,52,0,68,h,24,p.accent,true);
      text(comp,"unit",p.unit,129,0,62,h,16,p.ink,false);
    } else if(name==="reviewId") {
      text(comp,"reviewId",p.reviewId,12,0,104,h,26,p.accent,true);
      text(comp,"separator","/",116,0,24,h,26,p.ink,true);
      text(comp,"pointId",p.pointId,140,0,118,h,26,p.ink,true);
    } else if(name==="reviewLabel") {
      text(comp,"phaseLabel",p.phaseLabel,16,0,132,h,22,p.ink,false);
      var serverDot=box(comp,"server-dot",150,(h-7)/2,7,7,p.accent);
      serverDot.property("ADBE Root Vectors Group").property(1).property("ADBE Vectors Group").property(1).property("ADBE Vector Rect Roundness").setValue(3.5);
      text(comp,"serverText",p.serverPrefix+p.serverName,170,0,398,h,22,p.ink,false);
      text(comp,"serveLabel",p.serveLabel,584,0,140,h,22,p.accent,false);
    }
    report.push(name+" source="+spec.sha256+" controls="+comp.motionGraphicsTemplateControllerCount);
  }
  project.save(new File(cfg.outDir+"/tennis-native.aep"));
  for(var n=1;n<=project.numItems;n++) {
    var item=project.item(n);
    if(item instanceof CompItem && !item.exportAsMotionGraphicsTemplate(false,cfg.outDir))throw new Error("MOGRT export failed: "+item.name);
  }
  var result=new File(cfg.outDir+"/ae-generation.txt");result.encoding="UTF-8";
  if(!result.open("w"))throw new Error("Cannot save generation log");result.write(report.join("\\n"));result.close();
})();
`;
  return {source,manifest:{schema:'tennis-native-adapter/v1',templateVersion:mf.version,font,
    components:specs,propertyMap:{scoreboard:['rule','gamesLabel','pointsLabel','nameA','nameB','gamesA','gamesB','pointsA','pointsB','serverAOpacity','serverBOpacity'],serveLabel:['label'],serveSpeed:['qualifier','speed','unit'],reviewId:['reviewId','separator','pointId'],reviewLabel:['phaseLabel','serverText','serveLabel']},
    qualification:'authoring_script_only; AE execution and Premiere property/render tests required',
    note:'Native approximation of canonical layout; validate typography and bounds. Natural duration 120s; set and read back every instance duration.'}};
}
module.exports={build};
if(require.main===module) {
  const [output,font]=process.argv.slice(2);
  if(!output)throw new Error('Usage: node make_mogrt.cjs new-output-directory [PostScript-font-name]');
  if(fs.existsSync(output))throw new Error('Use a new output directory; existing authoring work is protected');
  const result=build(output,font);fs.mkdirSync(output,{recursive:true});
  fs.writeFileSync(path.join(output,'build-native.jsx'),result.source);
  fs.writeFileSync(path.join(output,'native-manifest.json'),JSON.stringify(result.manifest,null,2));
  console.log('Created an AE authoring script; no MOGRT has been generated or tested yet.');
}
