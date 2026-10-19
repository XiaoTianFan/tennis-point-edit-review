"""Verify or repair a materialized skill from its ASCII-safe text archive.

Only repairs the local copy on explicit --repair; never updates the saved skill.
"""
import argparse,base64,hashlib,json,zlib
from pathlib import Path

def archive_text(record):
    """Read text or compressed UTF-8; bound expansion and verify hashes."""
    if 'text' in record:
        text=record['text']
        if not isinstance(text,str):raise ValueError('Invalid archive text')
    elif record.get('encoding')=='zlib+base64':
        raw=base64.b64decode(record['data'],validate=True)
        # Expansion protection scales with the encoded input, not package size.
        budget=max(8*1024*1024,len(raw)*256)
        decoder=zlib.decompressobj()
        decoded=decoder.decompress(raw,budget+1)
        if len(decoded)>budget or not decoder.eof or decoder.unused_data:
            raise ValueError('Oversized or invalid compressed archive record')
        text=decoded.decode('utf-8')
    else:raise ValueError('Unknown archive encoding')
    if hashlib.sha256(text.encode('utf8')).hexdigest()!=record['sha256']:
        raise ValueError('Archive checksum mismatch')
    return text

def archive_files(backup):
    """v3 compresses the complete file map together; v1/v2 stay readable."""
    files=json.loads(archive_text(backup['payload'])) if backup.get('schema')=='tennis-recovery/v3' else backup['files']
    if not isinstance(files,dict) or not all(isinstance(k,str) and isinstance(v,dict) for k,v in files.items()):
        raise ValueError('Invalid archive file map')
    return files

def verify(root,repair=False):
    root=Path(root).resolve()
    backup=json.loads((root/'references/canonical-package.json').read_text(encoding='ascii'))
    changes=[]
    for name,record in archive_files(backup).items():
        text=archive_text(record);path=(root/name).resolve()
        if not path.is_relative_to(root):raise ValueError('Unsafe archive path')
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


