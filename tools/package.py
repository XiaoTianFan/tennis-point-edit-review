"""Offline package transport. No service login, network calls, commits or pushes."""
import argparse,hashlib,json,re,sys
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/tennis-point-edit-review'
ARCHIVE='references/canonical-package.json'
STATE=ROOT/'.skill-sync/baseline.json'
def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
def safe_name(name):
    p=PurePosixPath(name)
    if not name or p.is_absolute() or '\\' in name or ':' in name or any(x in ('','..','.') for x in name.split('/')):
        raise ValueError('Unsafe package path: '+name)
    if name not in ('SKILL.md','LICENSE') and (len(p.parts)<2 or p.parts[0] not in ('references','examples','scripts')):
        raise ValueError('Not a portable package path: '+name)
    return name
def read_package(root=SKILL):
    files={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():raise ValueError('Symlinks are not allowed in the package')
        if not p.is_file() or '__pycache__' in p.parts or p.suffix in ('.pyc','.pyo'):continue
        name=safe_name(p.relative_to(root).as_posix())
        files[name]=p.read_text(encoding='utf-8-sig')
    if 'SKILL.md' not in files:raise ValueError('Missing SKILL.md')
    return files
def with_archive(files):
    files={k:v.replace('\r\n','\n') for k,v in files.items() if k!=ARCHIVE}
    version=json.loads(files['references/package-version.json'])['version']
    archive={'version':version,'files':{k:{'text':v,'sha256':sha(v)} for k,v in sorted(files.items())}}
    files[ARCHIVE]=json.dumps(archive,ensure_ascii=True,separators=(',',':'))+'\n'
    if sum(len(v.encode()) for v in files.values())>=1000000:raise ValueError('Package exceeds 1 MB')
    return files
def load_snapshot(path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    recovered=[]
    if 'packageFiles' in data:data=data['packageFiles']
    elif isinstance(data.get('files'),dict) and all(isinstance(v,dict) and 'text' in v for v in data['files'].values()):
        data={ARCHIVE:json.dumps(data,ensure_ascii=True,separators=(',',':'))+'\n',
              **{k:v['text'] for k,v in data['files'].items()}}
    if not isinstance(data,dict) or not all(isinstance(v,str) for v in data.values()):
        raise ValueError('Expected a complete packageFiles mapping or recovery archive')
    data={safe_name(k):v.replace('\r\n','\n') for k,v in data.items()}
    if 'SKILL.md' not in data or 'references/package-version.json' not in data:
        raise ValueError('Incomplete package snapshot')
    if ARCHIVE in data:
        arc=json.loads(data[ARCHIVE])
        for name,entry in arc['files'].items():
            safe_name(name)
            if sha(entry['text'])!=entry['sha256']:raise ValueError('Invalid archive checksum: '+name)
            if name not in data:raise ValueError('Incomplete export: '+name)
            if data[name]!=entry['text']:
                if '\ufffd' in data[name] and '\ufffd' not in entry['text']:
                    data[name]=entry['text'];recovered.append(name)
                else:raise ValueError('Export and archive disagree: '+name)
    if any('\ufffd' in v for v in data.values()):raise ValueError('Unrecovered damaged Unicode')
    return with_archive(data),recovered
def fingerprints(files):
    return {k:sha(v) for k,v in files.items() if k!=ARCHIVE}
def plan_merge(local,incoming,baseline=None):
    base=baseline or {}
    lh,ih=fingerprints(local),fingerprints(incoming)
    writes=[];deletes=[];conflicts=[];preserved=[]
    for name in sorted(set(lh)|set(ih)|set(base)):
        l,i,b=lh.get(name),ih.get(name),base.get(name)
        if l==i:continue
        if l==b:
            (deletes if i is None else writes).append(name)
        elif i==b:
            preserved.append(name)
        else:
            conflicts.append(name)
    return {'write':writes,'delete':deletes,'conflicts':conflicts,'localOnlyChanges':preserved}
def apply_snapshot(local_root,incoming,plan,allow_deletes=False):
    if plan['conflicts']:raise ValueError('Conflicting files: '+', '.join(plan['conflicts']))
    if plan['delete'] and not allow_deletes:raise ValueError('Deletions need --allow-deletes')
    root=local_root.resolve()
    for name in plan['write']+plan['delete']:
        p=root/safe_name(name)
        if not p.resolve().is_relative_to(root):raise ValueError('Path escapes package')
        if p.is_symlink() or any(x.is_symlink() for x in p.parents if x!=root.parent):
            raise ValueError('Symlink destination')
    # Validate the entire resulting package before changing any file.
    merged=read_package(root)
    for name in plan['delete']:merged.pop(name,None)
    for name in plan['write']:merged[name]=incoming[name]
    merged=with_archive(merged)
    for name in plan['delete']:(root/name).unlink()
    for name in plan['write']+[ARCHIVE]:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(merged[name],encoding='utf-8',newline='')
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('refresh')
    exp=sub.add_parser('export');exp.add_argument('--output',required=True)
    for name in ('plan','import','baseline'):
        p=sub.add_parser(name);p.add_argument('--input',required=True)
        if name=='import':
            p.add_argument('--apply',action='store_true');p.add_argument('--allow-deletes',action='store_true')
    a=parser.parse_args()
    local=read_package()
    if a.command=='refresh':
        files=with_archive(local)
        (SKILL/ARCHIVE).write_text(files[ARCHIVE],encoding='ascii',newline='')
        print('Refreshed archive from current package files');return
    if a.command=='export':
        complete=with_archive(local)
        if complete[ARCHIVE]!=local.get(ARCHIVE):raise ValueError('Archive is stale: run refresh and validate')
        path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'schema':'tennis-skill-package/v1','packageFiles':complete},ensure_ascii=True,indent=2)+'\n',encoding='ascii',newline='')
        print('Exported portable package to '+str(path));return
    incoming,recovered=load_snapshot(a.input)
    if a.command=='baseline':
        if fingerprints(local)!=fingerprints(incoming):raise ValueError('Both snapshots must agree before setting baseline')
        STATE.parent.mkdir(parents=True,exist_ok=True)
        STATE.write_text(json.dumps({'files':fingerprints(incoming)},indent=2)+'\n',encoding='utf-8',newline='')
        print('Stored common baseline hashes; no account write was performed');return
    baseline=json.loads(STATE.read_text(encoding='utf-8'))['files'] if STATE.exists() else None
    plan=plan_merge(local,incoming,baseline)
    plan['recoveredUnicodeFiles']=recovered
    print(json.dumps(plan,ensure_ascii=True,indent=2))
    if a.command=='import' and a.apply:
        apply_snapshot(SKILL,incoming,plan,a.allow_deletes)
        STATE.parent.mkdir(parents=True,exist_ok=True)
        STATE.write_text(json.dumps({'files':fingerprints(incoming)},indent=2)+'\n',encoding='utf-8',newline='')
        print('Imported incoming changes; retained local-only changes. Validate before committing.')
    if plan['conflicts']:raise SystemExit(2)
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError) as e:
        print('Error: '+str(e),file=sys.stderr);raise SystemExit(1)
