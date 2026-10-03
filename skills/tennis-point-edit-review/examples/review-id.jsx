const Component=({item})=>{
 const props=item.props;
 const rootStyle={position:"absolute",inset:0,boxSizing:"border-box",display:"flex",alignItems:"center",justifyContent:"center",gap:12,background:props.transparentBackground?"transparent":props.panel,color:props.ink,fontFamily:props.font,fontSize:26,fontWeight:700,borderLeft:"5px solid "+props.accent,fontVariantNumeric:"tabular-nums"};
 const reviewStyle={color:props.accent};
 return <div style={rootStyle}><span style={reviewStyle}>{props.reviewId}</span><span>/</span><span>{props.pointId}</span></div>;
};


