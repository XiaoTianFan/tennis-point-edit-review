"""Verify or repair a materialized skill from its ASCII-safe text archive.

Only repairs the local copy on explicit --repair; never updates the saved skill.
"""
import argparse,hashlib,json
from pathlib import Path
def verify(root,repair=False):
    root=Path(root).resolve()
    backup=json.loads((root/'references/canonical-package.json').read_text(encoding='ascii'))
    changes=[]
    for name,record in backup['files'].items():
        text=record['text'];path=(root/name).resolve()
        if not path.is_relative_to(root):raise ValueError('Unsafe archive path')
        if hashlib.sha256(text.encode('utf8')).hexdigest()!=record['sha256']:raise ValueError('Archive checksum mismatch')
        actual=path.read_text(encoding='utf8') if path.exists() else None
        if actual!=text:
            changes.append(name)
            if repair:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(text,encoding='utf8',newline='\n')
    return {'matched':not changes,'repaired':changes if repair else [],'mismatches':[] if repair else changes,'version':backup['version']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repair',action='store_true');p.add_argument('--root',default=str(Path(__file__).resolve().parent.parent));a=p.parse_args()
    print(json.dumps(verify(a.root,a.repair),ensure_ascii=False,indent=2))


