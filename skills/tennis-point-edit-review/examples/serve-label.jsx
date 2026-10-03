const Component=({item})=>{
 const props=item.props;
 const rootStyle={position:"absolute",inset:0,display:"flex",alignItems:"center",justifyContent:"center",fontFamily:props.font,fontSize:27,fontWeight:700,background:props.transparentBackground?"transparent":props.panel,color:props.ink,borderLeft:"5px solid "+props.accent,boxSizing:"border-box"};
 return <div style={rootStyle}>{props.label}</div>;
};


