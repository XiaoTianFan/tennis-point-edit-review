"""Verify entry-rule preservation, original files, portability and approved templates."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
def verify():
    manifest=json.loads((ROOT/'references/reorganization-manifest.json').read_text(encoding='utf-8'))
    errors=[]
    for rule in manifest['entryRules']:
        path=ROOT/rule['target']
        lines=path.read_text(encoding='utf-8').splitlines()
        size=rule['requiredTextPrefixLength']
        if not any(digest(line[:size])==rule['requiredTextSha256'] for line in lines):
            errors.append('Missing adopted rule '+rule['id']+' in '+rule['target'])
    for record in manifest['originalFiles']:
        path=ROOT/record['path']
        if not path.is_file():
            errors.append('Missing original file: '+record['path'])
        elif record['status']=='unchanged' and digest(path.read_text(encoding='utf-8'))!=record['originalSha256']:
            errors.append('Unexpected change to retained file: '+record['path'])
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.suffix not in ('.md','.json','.jsx','.html','.py'):
            continue
        if p.name=='canonical-package.json':
            continue
        text=p.read_text(encoding='utf-8')
        # Project UUIDs and concrete camera-file names must never become reusable inputs.
        if re.search(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',text,re.I):
            errors.append('Project-specific UUID in '+str(p.relative_to(ROOT)))
        if re.search(r'\bIMG_\d+\.(?:MOV|MP4)\b',text,re.I):
            errors.append('Concrete video name in '+str(p.relative_to(ROOT)))
    if errors:
        raise ValueError('\n'.join(errors))
    return {'status':'passed','mappedEntryRules':len(manifest['entryRules']),
            'retainedOriginalFiles':len(manifest['originalFiles'])}
if __name__=='__main__':
    print(json.dumps(verify(),ensure_ascii=False,indent=2))

