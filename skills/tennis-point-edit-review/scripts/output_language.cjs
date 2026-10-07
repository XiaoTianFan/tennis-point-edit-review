// Presentation defaults only. Never translate caller overrides, evidence or IDs.
const en=require('../references/output-en.json');
function resolveLanguage(value='zh-CN') {
  const tag=value.toLowerCase().replaceAll('_','-');
  if(tag==='en'||tag.startsWith('en-'))return 'en';
  if(['zh','zh-cn','zh-hans','zh-hans-cn'].includes(tag))return 'zh-CN';
  throw new Error('Unsupported output language: '+value);
}
function localize(value,language) {
  if(Array.isArray(value))return value.map(v=>localize(v,language));
  if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,localize(v,language)]));
  if(typeof value==='string'&&language==='en') {
    if(!Object.hasOwn(en,value)&&/[\u3400-\u9fff]/.test(value))throw new Error('Missing English presentation text: '+value);
    return en[value]??value;
  }
  return value;
}
function defaultProps(component,language='zh-CN') {
  language=resolveLanguage(language);
  let props=Object.fromEntries(component.properties.map(p=>[p.key,p.defaultValue]));
  if('rows' in props)props.rows=JSON.parse(props.rows);
  props=localize(props,language);
  if('rows' in props)props.rows=JSON.stringify(props.rows);
  return props;
}
module.exports={resolveLanguage,defaultProps};
