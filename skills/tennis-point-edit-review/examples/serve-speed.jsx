const Component = ({ item }) => {
  const props = item.props;
  const rootStyle = {position:"absolute",inset:0,display:"flex",alignItems:"center",justifyContent:"center",gap:7,boxSizing:"border-box",background:props.panel,color:props.accent,borderLeft:"5px solid "+props.accent,fontFamily:props.font,padding:"0 9px 2px 6px",whiteSpace:"nowrap"};
  const qualifierStyle = {fontSize:15,fontWeight:500,color:props.ink,lineHeight:1};
  const valueStyle = {fontSize:24,fontWeight:700,fontVariantNumeric:"tabular-nums",lineHeight:1};
  const unitStyle = {fontSize:16,fontWeight:500,color:props.ink,lineHeight:1};
  return <div style={rootStyle}><span style={qualifierStyle}>{props.qualifier}</span><span style={valueStyle}>{props.speed}</span><span style={unitStyle}>{props.unit}</span></div>;
};


