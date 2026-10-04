"""Verify the distributed workflow contract and canonical assets."""
import hashlib,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'skills/tennis-point-edit-review'
CONTRACT=Path(__file__).with_name('fixtures')/'skill-contract.json'

def verify():
    contract=json.loads(CONTRACT.read_text(encoding='utf-8'))
    errors=[]
    for rule in contract['rules']:
        text=(ROOT/rule['path']).read_text(encoding='utf-8')
        if rule['text'] not in text:
            errors.append('Missing workflow rule '+rule['id']+' in '+rule['path'])
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
