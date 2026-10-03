const Component=({item})=>{
 const props=item.props;
 const rootStyle={position:"absolute",inset:0,boxSizing:"border-box",display:"flex",alignItems:"center",justifyContent:"center",gap:12,padding:"10px 18px",background:props.transparentBackground?"transparent":props.panel,color:props.ink,fontFamily:props.font,fontSize:22,fontWeight:600,borderLeft:"5px solid "+props.accent,whiteSpace:"nowrap"};
 const dotStyle={width:7,height:7,borderRadius:"50%",background:props.accent,flexShrink:0};
 const serveStyle={color:props.accent,fontWeight:700};
 return <div style={rootStyle}><span>{props.phaseLabel}</span><span style={dotStyle}/><span>{props.serverPrefix}{props.serverName}</span><span style={serveStyle}>{props.serveLabel}</span></div>;
};


