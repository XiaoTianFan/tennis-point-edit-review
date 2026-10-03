"""Check canonical package links, property contracts, versions and metric mapping."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def check():
    errors=[];mf=json.loads((ROOT/'examples/ui-manifest.json').read_text(encoding='utf8'))
    version=json.loads((ROOT/'references/package-version.json').read_text(encoding='utf8'))
    if mf['version']!=version['version']:errors.append('Version mismatch')
    if len(mf['components'])!=version['componentCount']:errors.append('Component count mismatch')
    if mf['version'] not in (ROOT/'SKILL.md').read_text(encoding='utf8'):errors.append('Entry version mismatch')
    for name,c in mf['components'].items():
        code=(ROOT/c['codeFile']).read_text(encoding='utf8')
        if hashlib.sha256(code.replace('\r\n','\n').encode('utf8')).hexdigest()!=c['sha256']:errors.append(name+': stale source hash')
        declared=[p['key'] for p in c['properties']]
        if len(declared)!=len(set(declared)):errors.append(name+': duplicate property')
        used=set(re.findall(r'props\.([A-Za-z0-9_]+)',code))
        if used-set(declared):errors.append(name+': undeclared properties '+str(used-set(declared)))
        if 'const Component' not in code or '<div style={rootStyle}>' not in code:errors.append(name+': invalid component contract')
    pages=json.loads((ROOT/mf['statsPages']).read_text(encoding='utf8'))
    if mf['components']['statsPanel']['rowCounts']!=[len(p['rows']) for p in pages]:errors.append('Manifest row counts mismatch')
    if mf['components']['statsPanel']['rowCounts']!=[len(p['rows']) for p in pages]:errors.append('Manifest row counts mismatch')
    if [len(p['rows']) for p in pages]!=[7,11,6,8,7]:errors.append('Wrong stats page counts')
    if sum(len(p['rows']) for p in pages)!=version['metricCount']:errors.append('Metric version mismatch')
    if pages[1]['rows'][3]['key']!='secondServeIn':errors.append('Second-serve-in not on serve page')
    for p in ROOT.rglob('*'):
        if p.suffix not in ('.md','.json','.jsx','.html','.py'):continue
        text=p.read_text(encoding='utf8')
        if '\ufffd' in text:errors.append(str(p.relative_to(ROOT))+': damaged encoding')
        if p.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',text):
                if re.match(r'\w+://',target) or target.startswith('#'):continue
                if not (p.parent/target.split('#')[0]).exists():errors.append('Broken link: '+target)
    if errors:raise ValueError('\n'.join(errors))
    return {'version':mf['version'],'componentCount':len(mf['components']),'metricCount':sum(len(p['rows']) for p in pages),'status':'passed'}
if __name__=='__main__':print(json.dumps(check(),ensure_ascii=False,indent=2))


