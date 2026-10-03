"""Run package and repository checks; never edit or publish the package."""
import json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'skills/tennis-point-edit-review'
def run(args,cwd=ROOT):
    subprocess.run([sys.executable,'-B',*args],cwd=cwd,check=True)
def main():
    run(['-m','unittest','discover','-p','check_*.py'],PACKAGE/'scripts')
    run(['-m','unittest','discover','-s','tools','-p','test_*.py'])
    for name in ('package_check.py','check_reorganization.py','restore_package.py'):
        run(['scripts/'+name],PACKAGE)
    from importlib.util import spec_from_file_location,module_from_spec
    spec=spec_from_file_location('restore',PACKAGE/'scripts/restore_package.py')
    module=module_from_spec(spec);spec.loader.exec_module(module)
    if not module.verify(PACKAGE)['matched']:raise ValueError('Package archive is stale')
    listed=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    bad=[]
    for name in set(listed):
        if not name:continue
        p=ROOT/name
        if not p.is_file() or p.suffix.lower() not in ('.md','.json','.py','.cjs','.js','.html','.yml','.yaml','.txt','.jsx'):continue
        content=p.read_text(encoding='utf-8')
        if '\ufffd' in content:bad.append(name+': damaged Unicode')
        if re.search(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',content,re.I):bad.append(name+': private identifier')
        if re.search(r'\bIMG_\d+\.(MOV|MP4)\b',content,re.I):bad.append(name+': real camera filename')
        if p.suffix=='.md':
            for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',content):
                if re.match(r'\w+://',target) or target.startswith('#'):continue
                if not (p.parent/target.split('#')[0]).exists():bad.append(name+': missing link '+target)
    if bad:raise ValueError('\n'.join(bad))
    print('Repository checks passed: links, package integrity, portable source and synthetic demos.')
if __name__=='__main__':main()
