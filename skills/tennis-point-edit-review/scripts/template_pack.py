"""Portable template bundles; no project writes and no product API dependency."""
import argparse,copy,hashlib,json,math,unicodedata
from stat_comparison import direction,compare
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def text_units(text):return sum(1 if unicodedata.east_asian_width(c) in 'WF' else .56 for c in str(text))

def bundle(component, overrides=None):
    manifest=read(ROOT/'examples/ui-manifest.json')
    c=copy.deepcopy(manifest['components'][component]);code=(ROOT/c['codeFile']).read_text(encoding='utf8')
    if hashlib.sha256(code.replace('\r\n','\n').encode('utf8')).hexdigest()!=c['sha256']:raise ValueError('Template version/hash mismatch')
    props={p['key']:p['defaultValue'] for p in c['properties']};overrides=overrides or {}
    if set(overrides)-set(props):raise ValueError('Unknown editable property')
    props.update(overrides)
    for p in c['properties']:p['defaultValue']=props[p['key']]
    warnings=[]
    if component=='explanation':
        # Conservative wrapping estimate only; browser/font metrics must verify it.
        lines=sum(max(1,math.ceil(text_units(s)*21/936)) for s in props['detail'].split('\n'))
        title_lines=max(1,math.ceil(text_units(props['title'])*25/936))
        h=max(132,math.ceil(37+title_lines*31.25+7+lines*29.4+2))
        c['naturalSize']['height']=h;c['placement1080p']['height']=h*.8
        if lines>3:warnings.append('Shorten explanation or paginate; do not hide overflow or cover the court')
    if component=='statsPanel':
        rows=json.loads(props['rows'])
        if len(rows)>11:raise ValueError('At most eleven rows per stats page; paginate')
        if props['panelFrames']<20:raise ValueError('Too short for panel fade and reading')
    return {'templateVersion':manifest['version'],'component':component,'code':code,'properties':c['properties'],'props':props,'naturalSize':c['naturalSize'],'placement1080p':c['placement1080p'],'warnings':warnings,'verification':'Preview composed target frames before delivery'}

def display(value, speed=False):
    if value is None:return '待核'
    if isinstance(value,dict):
        n,d=value['numerator'],value['denominator']
        if d==0:return '—（0/0）'
        return f'{100*n/d:g}%  ({n}/{d})' if (100*n/d).is_integer() else f'{100*n/d:.1f}%  ({n}/{d})'
    if speed:return f'约 {value:.0f} km/h'
    return str(value)

def build_stats_pages(metrics, speed_summary, diagnostics=None):
    """Caller selects one set/match scope; old geometric speed keys are never used."""
    pages=read(ROOT/'examples/stats-pages.json')
    keys={'fastestServeLaunchKph':'fastestServeKphEstimate','allServeMeanLaunchKph':'allServeMeanKphEstimate','firstServeMeanLaunchKph':'firstServeMeanKphEstimate','secondServeMeanLaunchKph':'secondServeMeanKphEstimate'}
    for page in pages:
        for row in page['rows']:
            values={}
            for player,col in [('A','a'),('B','b')]:
                if row['key'] in keys:
                    value=speed_summary[player].get(keys[row['key']])
                    if value is None:
                        n='firstServeCount' if row['key']=='firstServeMeanLaunchKph' else 'secondServeCount' if row['key']=='secondServeMeanLaunchKph' else 'count'
                        if speed_summary[player].get(n)==0:row[col]='—（无该类发球）';values[player]=None;continue
                        raise ValueError('Complete launch estimates or documented no-serve scope required')
                    row[col]=display(value,True)
                else:
                    value=metrics[player].get(row['key'])
                    if value is None:raise ValueError('Complete reviewed event metrics before final panel assembly: '+row['key'])
                    row[col]=display(value)
                values[player]=value
            row['comparison']=direction(row['key'])
            row['highlight']=compare(row['key'],values['A'],values['B'],row['a'],row['b'])
            row['comparisonValues']=values
            if row['key'] == 'FE':
                ua=metrics['A'].get('unclassifiedErrors',0);ub=metrics['B'].get('unclassifiedErrors',0)
                if ua or ub:
                    row['highlight']='A' if values['A']+ua<values['B'] else 'B' if values['B']+ub<values['A'] else None
            if row['key'] in ('shortWinRate','mediumWinRate','longWinRate'):
                if diagnostics is None:raise ValueError('Rally frequency requires reviewed diagnostic scope')
                k=row['key'].replace('WinRate','');row['sub']='回合占比 '+display(diagnostics['rallyDistribution'][k])
            if row['key'] in ('winners','UE','FE'):
                k='W' if row['key']=='winners' else row['key']
                for player,col in [('A','asub'),('B','bsub')]:
                    h=metrics[player]['terminalHands'][k]
                    row[col]=f'正手 {h["FH"]} · 反手 {h["BH"]}'
                    if h.get('other'):row[col]+=f' · 其他 {h["other"]}'
                    if h.get('unknown'):row[col]+=f' · 未判 {h["unknown"]}'
        if page['page']==5:
            for player,col in [('A','asub'),('B','bsub')]:
                n=metrics[player].get('ueMotionCounts',{}).get('unknown',0)
                if n:page['rows'][0][col]=f'另有 {n} 次 UE 动作未判'
    return pages

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('component');p.add_argument('--props');p.add_argument('--output',required=True);a=p.parse_args()
    out=bundle(a.component,read(a.props) if a.props else {})
    Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
