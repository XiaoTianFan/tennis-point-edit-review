"""Verify the distributed workflow contract and canonical assets."""
import hashlib,json,re
from pathlib import Path
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]/'skills/tennis-point-edit-review'
CONTRACT=Path(__file__).with_name('fixtures')/'skill-contract.json'

def check_rules(root, rules):
    errors=[]
    for rule in rules:
        checks=rule.get('checks', [rule] if 'text' in rule else [])
        if not checks:
            errors.append('Empty workflow rule '+rule['id'])
        for check in checks:
            path=root/check['path']
            if not check.get('text') or not path.is_file() or check['text'] not in path.read_text(encoding='utf-8'):
                errors.append('Missing workflow rule '+rule['id']+' in '+check['path'])
    return errors

def check_section_links(root):
    """Check local Markdown headings, including links back into the same file."""
    errors=[]; headings={}
    for p in root.rglob('*.md'):
        slugs=set(); counts={}
        for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$',p.read_text(encoding='utf-8'),re.M):
            slug=re.sub(r'[^\w\- ]','',heading.lower()).replace(' ','-')
            count=counts.get(slug,0);counts[slug]=count+1
            slugs.add(slug+(('-'+str(count)) if count else ''))
        headings[p.resolve()]=slugs
    for p in root.rglob('*.md'):
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if re.match(r'\w+://',target):continue
            file,sep,anchor=target.partition('#')
            dest=(p.parent/file).resolve() if file else p.resolve()
            if sep and anchor and dest.suffix=='.md' and unquote(anchor) not in headings.get(dest,set()):
                errors.append('Broken section link in '+str(p.relative_to(root))+': '+target)
    return errors

def verify():
    contract=json.loads(CONTRACT.read_text(encoding='utf-8'))
    errors=check_rules(ROOT,contract['rules'])+check_section_links(ROOT)
    for record in contract['files']:
        path=ROOT/record['path']
        if not path.is_file():
            errors.append('Missing runtime file: '+record['path'])
        elif 'sha256' in record and hashlib.sha256(path.read_text(encoding='utf-8').encode()).hexdigest()!=record['sha256']:
            errors.append('Changed protected asset: '+record['path'])
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.suffix not in ('.md','.json','.jsx','.html','.py') or p.name=='canonical-package.json':
            continue
        text=p.read_text(encoding='utf-8')
        if re.search(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',text,re.I):
            errors.append('Project-specific UUID in '+str(p.relative_to(ROOT)))
        if re.search(r'\bIMG_\d+\.(?:MOV|MP4)\b',text,re.I):
            errors.append('Concrete video name in '+str(p.relative_to(ROOT)))
    if errors:
        raise ValueError('\n'.join(errors))
    return {'status':'passed','workflowRules':len(contract['rules']),'runtimeFiles':len(contract['files'])}

if __name__=='__main__':
    print(json.dumps(verify(),ensure_ascii=False,indent=2))
