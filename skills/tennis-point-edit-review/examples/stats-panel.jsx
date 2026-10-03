const Component=({item})=>{
const frame=useCurrentFrame();const props=item.props;const rowsData=JSON.parse(props.rows);
const alpha=interpolate(frame,[0,9,props.panelFrames-9,props.panelFrames-1],[0,1,1,0],{extrapolateLeft:"clamp",extrapolateRight:"clamp"});
const rootStyle={position:"absolute",inset:0,display:"flex",flexDirection:"column",boxSizing:"border-box",padding:"25px 44px 25px",backgroundColor:props.transparentBackground?"transparent":props.panel,color:props.ink,fontFamily:props.font,borderTop:"5px solid "+props.accent,opacity:alpha};
const heading={display:"flex",justifyContent:"space-between",alignItems:"center",height:54,flexShrink:0};
const titleStyle={fontSize:40,fontWeight:700};
const countStyle={fontSize:27,color:props.accent,fontVariantNumeric:"tabular-nums"};
const subtitleStyle={height:36,flexShrink:0,fontSize:25,opacity:.82};
const namesStyle={display:"grid",gridTemplateColumns:"400px 1fr 400px",height:60,flexShrink:0,alignItems:"center",marginTop:10,backgroundColor:props.header,borderBottom:"2px solid "+props.accent,textAlign:"center",fontSize:34,fontWeight:700};
const centerStyle={fontSize:23,letterSpacing:3,color:props.accent};
const bodyStyle={flex:1,display:"flex",flexDirection:"column",justifyContent:"center",minHeight:0};
const rowStyle={display:"grid",gridTemplateColumns:"400px 1fr 400px",minHeight:rowsData.length>8?50:64,flexShrink:0,alignItems:"center",textAlign:"center",borderBottom:"1px solid rgba(245,247,250,.15)",padding:"4px 0",boxSizing:"border-box"};
const valueStyle={fontSize:30,fontWeight:600,fontVariantNumeric:"tabular-nums",lineHeight:1.25};
const labelStyle={fontSize:27,fontWeight:500,lineHeight:1.25};
const subStyle={fontSize:21,lineHeight:1.35,opacity:.8,fontWeight:400};
const footerStyle={display:"flex",flexDirection:"column",justifyContent:"flex-end",gap:5,minHeight:108,flexShrink:0,fontSize:21,lineHeight:1.4};
const footStyle={opacity:.8};
const disclaimerStyle={color:props.accent,fontSize:23};
const rows=rowsData.map((r,i)=><div key={i} style={rowStyle}><div style={valueStyle}><span style={{color:r.highlight==="A"?props.accent:props.ink}}>{r.a}</span>{r.asub&&<div style={subStyle}>{r.asub}</div>}</div><div style={labelStyle}>{r.label}{r.sub&&<div style={subStyle}>{r.sub}</div>}</div><div style={valueStyle}><span style={{color:r.highlight==="B"?props.accent:props.ink}}>{r.b}</span>{r.bsub&&<div style={subStyle}>{r.bsub}</div>}</div></div>);
return <div style={rootStyle}><div style={heading}><span style={titleStyle}>{props.title}</span><span style={countStyle}>{props.pageNumber}</span></div><div style={subtitleStyle}>{props.subtitle}</div><div style={namesStyle}><span>{props.nameA}</span><span style={centerStyle}>{props.eyebrow}</span><span>{props.nameB}</span></div><div style={bodyStyle}>{rows}</div><div style={footerStyle}><span style={footStyle}>{props.footnote}</span><span style={footStyle}>{props.footnote2}</span><span style={disclaimerStyle}>{props.disclaimer}</span></div></div>;
};

