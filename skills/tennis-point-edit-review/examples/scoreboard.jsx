const Component=({item})=>{
const frame=useCurrentFrame(); const props=item.props;
const opacity=1;
const rootStyle={position:"absolute",inset:0,fontFamily:props.font,color:props.ink,background:props.transparentBackground?"transparent":props.panel,fontVariantNumeric:"tabular-nums",opacity,display:"flex",flexDirection:"column",overflow:"hidden"};
const headerStyle={height:28,flexShrink:0,display:"grid",gridTemplateColumns:"1fr 56px 68px",alignItems:"center",background:props.header,fontSize:13,fontWeight:600};
const rowStyle={height:52,display:"grid",gridTemplateColumns:"28px 1fr 56px 68px",alignItems:"center",background:props.panel};
const nameStyle={fontSize:23,fontWeight:600,whiteSpace:"nowrap",overflow:"hidden"};
const gameStyle={height:"100%",display:"flex",alignItems:"center",justifyContent:"center",fontSize:28,fontWeight:600,background:props.header};
const pointStyle={...gameStyle,color:props.header,background:props.accent,fontWeight:700,fontSize:30};
const dotStyle={width:6,height:6,borderRadius:"50%",background:props.accent,justifySelf:"center",opacity:0};
const rows=[{name:props.nameA,game:props.gamesA,point:props.pointsA},{name:props.nameB,game:props.gamesB,point:props.pointsB}];
return <div style={rootStyle}><div style={headerStyle}><div style={{paddingLeft:12,color:props.accent}}>{props.rule}</div><div style={{textAlign:"center"}}>{props.gamesLabel}</div><div style={{textAlign:"center"}}>{props.pointsLabel}</div></div>{rows.map((r,i)=><div key={i} style={rowStyle}><div style={{...dotStyle,opacity:props.server===(i===0?"A":"B")?1:0}}/><div style={nameStyle}>{r.name}</div><div style={gameStyle}>{r.game}</div><div style={pointStyle}>{r.point}</div></div>)}</div>;
};


