"""Owned procedural images, explicit evidence promotion and resumable cleanup.

Only put() creates deletion authority. No importing existing files, recursive
deletion, age policy or extension-based discovery. Canonical records stay outside.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat


def safe(path):
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents), path]:
        if not part.exists() and not part.is_symlink():
            continue
        s = part.lstat()
        if stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Symlink/reparse path rejected: ' + str(part))
        if part.is_file() and s.st_nlink != 1:
            raise ValueError('Hardlinked file rejected: ' + str(part))
    return path


def digest(path):
    path = safe(path); before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    after = path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns) != (after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('File changed during verification')
    return dict(size=after.st_size, mtimeNs=after.st_mtime_ns, inode=after.st_ino,
                device=after.st_dev, sha256=h.hexdigest())


def same(path, expected):
    if digest(path) != expected: raise ValueError('Changed file: ' + str(path))


def load(path):
    return json.loads(safe(path).read_text(encoding='utf-8'))


def save(path, value, exclusive=False):
    path = safe(path)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    if exclusive:
        with path.open('xb') as f: f.write(payload); f.flush(); os.fsync(f.fileno())
        return
    temporary = path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
    with temporary.open('xb') as f: f.write(payload); f.flush(); os.fsync(f.fileno())
    safe(path); os.replace(temporary, path)


class Stage:
    @classmethod
    def create(cls, job, purpose):
        job = safe(job)
        if not job.is_dir(): raise ValueError('Existing job directory required')
        if purpose not in ('navigation','movement','stroke','boundary','line','net','contact','speed'):
            raise ValueError('Declare the inspection purpose')
        parent = safe(job/'.stage-cache'); parent.mkdir(exist_ok=True)
        root = parent/secrets.token_hex(12); root.mkdir()
        (root/'data').mkdir()
        save(root/'owner.json', dict(schema='tennis-stage-cache/v1', stageId=root.name,
             job=str(job), root=str(root), purpose=purpose), exclusive=True)
        save(root/'manifest.json', dict(state='active', artifacts={}, indexes={}), exclusive=True)
        (root/'lock').write_bytes(b'0')
        return cls(root)

    def __init__(self, root):
        self.root = safe(root)
        self.owner = load(self.root/'owner.json')
        self.job = safe(self.owner['job'])
        if (self.owner.get('schema') != 'tennis-stage-cache/v1' or self.root != self.job/'.stage-cache'/self.owner['stageId']
                or str(self.root) != self.owner['root']):
            raise ValueError('Invalid stage ownership')

    @contextmanager
    def locked(self):
        safe(self.root)
        with safe(self.root/'lock').open('r+b') as lock:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try: yield
            finally:
                if os.name == 'nt': lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else: fcntl.flock(lock, fcntl.LOCK_UN)

    def put(self, name, data):
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.(png|jpg|webp)', name):
            raise ValueError('A simple generated image name is required')
        # Image bytes only; authority is the exclusive creation record, not suffix.
        from PIL import Image
        import io
        with Image.open(io.BytesIO(data)) as image: image.verify()
        with self.locked():
            manifest = load(self.root/'manifest.json')
            if manifest['state'] != 'active': raise ValueError('Stage is sealed')
            path = safe(self.root/'data'/name)
            with path.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
            manifest['artifacts'][name] = dict(path=str(path), **digest(path))
            save(self.root/'manifest.json', manifest)
        return str(path)

    def index(self, path):
        """Register the helper's numeric JSON catalog, never a disposable artifact."""
        path = safe(path)
        if not path.is_relative_to(self.job) or path.is_relative_to(self.job/'.stage-cache') or path.suffix != '.json':
            raise ValueError('Index must be canonical JSON inside the job, outside the cache')
        with self.locked():
            manifest = load(self.root/'manifest.json')
            if manifest['state'] != 'active': raise ValueError('Stage is sealed')
            manifest['indexes'][str(path)] = digest(path)
            save(self.root/'manifest.json', manifest)

    def _rewrite(self, value, replacements):
        if isinstance(value, str): return replacements.get(value, value)
        if isinstance(value, list): return [self._rewrite(x,replacements) for x in value]
        if isinstance(value, dict): return {k:self._rewrite(v,replacements) for k,v in value.items()}
        return value

    def _canonical(self):
        # Read-only reference inventory. Never follow directory links or traverse cache.
        count = 0
        for folder, dirs, files in os.walk(self.job, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(folder)==self.job and d=='.stage-cache')]
            for name in dirs: safe(Path(folder)/name)
            for name in files:
                path = safe(Path(folder)/name)
                if path.suffix.lower() not in ('.json','.jsonl','.md','.csv','.txt'): continue
                count += 1
                if count > 20000 or path.stat().st_size > 64*1024*1024:
                    raise ValueError('Canonical inventory too large; use a bounded job directory')
                yield path

    def _check_references(self, artifacts, updates=None):
        for path in self._canonical():
            value = json.dumps(updates[str(path)],ensure_ascii=False) if updates and str(path) in updates else path.read_text(encoding='utf-8')
            if (self.owner['stageId'] in value and '.stage-cache' in value) or any('data/'+n in value.replace('\\','/') for n in artifacts):
                raise ValueError('Canonical record still references cache: '+str(path))

    def finish(self, observations=None):
        """Persist a cleanup plan once; later calls resume exactly that plan.

        observations: JSON with stageId, reviewed=true, nonempty observations,
        essentialArtifacts (names). An adopted precision conclusion needs a key
        image; unadopted/inconclusive stages may retain only numeric observations.
        """
        with self.locked():
            manifest = load(self.root/'manifest.json')
            plan_path = self.root/'cleanup-plan.json'
            if not plan_path.exists():
                if manifest['state'] != 'active': raise ValueError('Invalid stage state')
                obs = safe(observations) if observations else None
                if not obs or not obs.is_relative_to(self.job) or obs.is_relative_to(self.job/'.stage-cache'):
                    raise ValueError('Persist observations outside cache in this job first')
                record = load(obs)
                if record.get('stageId') != self.owner['stageId'] or record.get('reviewed') is not True or not record.get('observations'):
                    raise ValueError('Actual readback and persisted observations are required')
                keep = record.get('essentialArtifacts')
                if not isinstance(keep,list) or any(x not in manifest['artifacts'] for x in keep) or len(set(keep)) != len(keep):
                    raise ValueError('List essential artifact names explicitly, or []')
                if record.get('adopted') and self.owner['purpose'] in ('line','net','contact','speed') and not keep:
                    raise ValueError('Promote key evidence for the adopted precision conclusion')
                for name, item in manifest['artifacts'].items():
                    if Path(item['path']) != self.root/'data'/name: raise ValueError('Invalid artifact ownership')
                    same(item['path'], {k:v for k,v in item.items() if k!='path'})
                for path, expected in manifest['indexes'].items(): same(path,expected)
                destination = self.job/'evidence'/self.owner['stageId']
                replacements = {}
                for name,item in manifest['artifacts'].items():
                    result = str(destination/name) if name in keep else None
                    replacements[item['path']] = result
                    replacements[str(Path(item['path']).relative_to(self.job))] = result
                    replacements[Path(item['path']).relative_to(self.job).as_posix()] = result
                updates = {p:self._rewrite(load(p),replacements) for p in manifest['indexes']}
                self._check_references(manifest['artifacts'],updates)
                protected = {}
                for path in self._canonical():
                    value = json.dumps(updates[str(path)],ensure_ascii=False) if str(path) in updates else path.read_text(encoding='utf-8')
                    # Any remaining reference (including embedded prose/relative names)
                    # must be reconciled explicitly before any deletion.
                    if (self.owner['stageId'] in value and '.stage-cache' in value) or any(('data/'+n in value.replace('\\','/')) for n in manifest['artifacts']):
                        raise ValueError('Canonical record still references cache: '+str(path))
                    if str(path) not in updates: protected[str(path)] = digest(path)
                plan = dict(schema='tennis-stage-cleanup/v1', stageId=self.owner['stageId'],
                            artifacts=manifest['artifacts'], keep=keep, destination=str(destination),
                            indexBefore=manifest['indexes'], indexAfter=updates, protected=protected,
                            observations=str(obs), observationIdentity=digest(obs))
                save(plan_path,plan,exclusive=True)
            plan = load(plan_path)
            if plan['stageId'] != self.owner['stageId'] or plan['artifacts'] != manifest['artifacts']:
                raise ValueError('Cleanup plan ownership mismatch')
            outcome_path = self.root/'outcome.json'
            outcome = load(outcome_path) if outcome_path.exists() else dict(planSha256=digest(plan_path)['sha256'],deleted=[],promoted={},state='cleaning')
            if outcome['planSha256'] != digest(plan_path)['sha256']: raise ValueError('Cleanup plan changed')
            for p, expected in plan['protected'].items(): same(p,expected)
            same(plan['observations'],plan['observationIdentity'])
            save(outcome_path,outcome)
            destination = safe(plan['destination'])
            if destination != self.job/'evidence'/self.owner['stageId']: raise ValueError('Invalid promotion path')
            if plan['keep']:
                safe(destination.parent).mkdir(exist_ok=True)
                destination.mkdir(exist_ok=True)
            for name in plan['keep']:
                item = plan['artifacts'][name]; target = safe(destination/name)
                if not target.exists():
                    same(item['path'], {k:v for k,v in item.items() if k!='path'})
                    with target.open('xb') as dest, safe(item['path']).open('rb') as src:
                        import shutil
                        shutil.copyfileobj(src,dest,1024*1024); dest.flush(); os.fsync(dest.fileno())
                if digest(target)['sha256'] != item['sha256']: raise ValueError('Promotion verification failed')
                outcome['promoted'][name] = str(target)
            # Numeric data survives; only catalog image references become retained paths
            # or null. Per-image availability and recipe remain in this immutable plan.
            for p, after in plan['indexAfter'].items():
                if load(p) != after:
                    same(p,plan['indexBefore'][p]); save(p,after)
            manifest['state']='cleaning'; save(self.root/'manifest.json',manifest)
            save(outcome_path,outcome)
            self._check_references(plan['artifacts'])  # Includes new records on resume.
            for name,item in plan['artifacts'].items():
                path = safe(item['path'])
                if path != self.root/'data'/name: raise ValueError('Invalid deletion path')
                if name in outcome['deleted']:
                    if path.exists(): raise ValueError('Deleted artifact reappeared')
                    continue
                if path.exists():
                    same(path,{k:v for k,v in item.items() if k!='path'})
                    path.unlink()
                # Crash after unlink but before journal save is idempotent.
                outcome['deleted'].append(name); save(outcome_path,outcome)
            for p, expected in plan['protected'].items(): same(p,expected)
            for p, after in plan['indexAfter'].items():
                if load(p) != after: raise ValueError('Canonical index changed during cleanup')
            self._check_references(plan['artifacts'])
            outcome.update(state='cleaned',deletedBytes=sum(x['size'] for x in plan['artifacts'].values()),
                           retainedBytes=sum(plan['artifacts'][n]['size'] for n in plan['keep']))
            manifest['state']='cleaned'; save(self.root/'manifest.json',manifest); save(outcome_path,outcome)
            return outcome


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('create'); c.add_argument('job'); c.add_argument('--purpose',required=True)
    f=sub.add_parser('finish'); f.add_argument('stage'); f.add_argument('--observations')
    a=p.parse_args()
    result={'stage':str(Stage.create(a.job,a.purpose).root)} if a.command=='create' else Stage(a.stage).finish(a.observations)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
