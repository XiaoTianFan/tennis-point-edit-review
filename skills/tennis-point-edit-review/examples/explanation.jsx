const Component=({item})=>{
const props=item.props;
const rootStyle={position:"absolute",inset:0,boxSizing:"border-box",padding:"17px 22px 20px",borderLeft:"4px solid "+props.accent,background:props.transparentBackground?"transparent":props.header,color:props.ink,fontFamily:props.font,display:"flex",flexDirection:"column",gap:7};
const titleStyle={fontSize:25,fontWeight:700,lineHeight:1.25,color:props.accent,flexShrink:0};
const detailStyle={fontSize:21,lineHeight:1.4,whiteSpace:"normal",overflowWrap:"break-word",flexShrink:0};
return <div style={rootStyle}><div style={titleStyle}>{props.title}</div><div style={detailStyle}>{props.detail}</div></div>;
};


