"""Opt-in full-stream WASB observations with immutable chunks and resumable commits.

This does not infer tennis points, adopt answers, or modify an editor project.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import secrets
import time

import av

from cv_wasb import WASB, configuration
from job_workspace import safe_path
from media_probe import identity, metadata
from source_binding import unchanged

SCHEMA = 'tennis-vision-stream/v1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.'+secrets.token_hex(6)+'.pending')
    with temporary.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temporary, path)


@contextmanager
def locked(directory):
    with (directory/'run.lock').open('a+b') as f:
        if f.tell()==0:
            f.write(b'0'); f.flush()
        f.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name=='nt':
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def validate_chunks(directory, state):
    count=0; previous=None
    for chunk in state['chunks']:
        if Path(chunk['file']).name!=chunk['file'] or not chunk['file'].endswith('.jsonl'):
            raise ValueError('Invalid chunk name')
        path=safe_path(directory/'chunks'/chunk['file'])
        if path.parent!=directory/'chunks' or identity(path)['sha256']!=chunk['sha256']:
            raise ValueError('Committed observation chunk changed')
        rows=0; first=None; last=None
        with path.open(encoding='utf-8') as f:
            for line in f:
                row=json.loads(line); seconds=Fraction(row['pts'])*Fraction(row['timeBase'])
                if row['id']!=f'F{count:09}' or seconds!=Fraction(row['seconds']) or previous is not None and seconds<=previous:
                    raise ValueError('Committed frame identities or PTS are inconsistent')
                if first is None:first=row['seconds']
                last=row['seconds'];previous=seconds;count+=1;rows+=1
        if rows!=chunk['frames'] or first!=chunk['firstSeconds'] or last!=chunk['lastSeconds']:
            raise ValueError('Chunk coverage disagrees with commit')
    if count!=state['frames'] or (str(previous) if previous is not None else None)!=state['lastSeconds']:
        raise ValueError('Journal coverage disagrees with chunks')


def decoded(source, state, maximum):
    """Seek to the committed frame, verify it, then yield every later actual PTS."""
    last=Fraction(state['lastSeconds']) if state['lastSeconds'] is not None else None
    previous=None; count=state['frames']; boundary_seen=last is None
    with av.open(source) as container:
        stream=container.streams.video[0]
        if last is not None:
            container.seek(int(last/stream.time_base), stream=stream, backward=True, any_frame=False)
        for frame in container.decode(stream):
            if frame.pts is None:raise ValueError('Missing source PTS')
            seconds=frame.pts*frame.time_base
            if previous is not None and seconds<=previous:raise ValueError('Nonmonotone source PTS')
            previous=seconds
            if last is not None and seconds<=last:
                if seconds==last:boundary_seen=True
                continue
            if not boundary_seen:raise ValueError('Resume seek did not reproduce the committed boundary')
            if count>=maximum:raise ValueError('Frame budget exhausted; no complete result published')
            row=dict(id=f'F{count:09}',pts=frame.pts,timeBase=str(frame.time_base),seconds=str(seconds),
                     nativeSize=[frame.width,frame.height],coordinateSpace='original encoded pixels',
                     track=None,adjudication=None,interpolated=False)
            yield row,frame
            count+=1
        if not boundary_seen:raise ValueError('Resume boundary missing')


def scan(source, directory, value, resume=False, stop_after_chunks=None):
    started=time.perf_counter();config=configuration(value)
    if stop_after_chunks is not None and (type(stop_after_chunks) is not int or stop_after_chunks<1):
        raise ValueError('stop_after_chunks must be positive')
    directory=safe_path(directory)
    if directory.exists() and not resume:raise ValueError('Existing run requires explicit resume')
    if resume and not (directory/'state.json').is_file():raise ValueError('No committed run to resume')
    source=identity(source);probe=metadata(source['path'])
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    if video.get('color_transfer') in ('smpte2084','arib-std-b67') or video.get('sample_aspect_ratio','1:1') not in ('1:1','0:1','N/A') or any(float(s.get('rotation',0))%360 for s in video.get('side_data_list',[])):
        raise ValueError('This detector requires SDR, unrotated square-pixel input')
    code={name:identity(Path(__file__).with_name(name))['sha256'] for name in
          ('cv_stream.py','cv_wasb.py','media_probe.py','source_binding.py')}
    external={k:identity(config[k]) for k in ('module','modelConfig','weights')}
    fence=dict(schema=SCHEMA,sourceIdentity=source,config=config,code=code,external=external)
    run_id=hashlib.sha256(json.dumps(fence,sort_keys=True).encode()).hexdigest()
    directory.mkdir(parents=True,exist_ok=resume)
    with locked(directory):
        if resume:
            state=read(directory/'state.json')
            if state.get('runId')!=run_id:raise ValueError('Source, configuration, implementation or weights changed; start a new run')
            validate_chunks(directory,state)
            if state['status']=='complete':
                if identity(directory/'result.json')['sha256']!=state['resultSha256']:
                    raise ValueError('Completed result changed')
                return read(directory/'result.json')
        else:
            (directory/'chunks').mkdir()
            state=dict(**fence,runId=run_id,sourceProbe=probe,status='running',chunks=[],frames=0,
                       firstSeconds=None,lastSeconds=None,attempts=[])
        attempt=dict(startedAt=datetime.now(timezone.utc).isoformat(),fromFrame=state['frames'],status='running')
        state['attempts'].append(attempt);state['status']='running';save(directory/'state.json',state)
        chunk_rows=[]; committed=0

        def commit():
            nonlocal chunk_rows, committed
            if not chunk_rows:return
            unchanged(source)
            for fp in external.values():unchanged(fp)
            name=f"{len(state['chunks']):06}-{secrets.token_hex(6)}.jsonl"
            path=directory/'chunks'/name
            with path.open('x',encoding='utf-8') as f:
                for row in chunk_rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
                f.flush();os.fsync(f.fileno())
            state['chunks'].append(dict(file=name,sha256=identity(path)['sha256'],frames=len(chunk_rows),
                firstSeconds=chunk_rows[0]['seconds'],lastSeconds=chunk_rows[-1]['seconds']))
            if state['firstSeconds'] is None:state['firstSeconds']=chunk_rows[0]['seconds']
            state['frames']+=len(chunk_rows);state['lastSeconds']=chunk_rows[-1]['seconds']
            attempt['wallSeconds']=time.perf_counter()-started
            save(directory/'state.json',state);chunk_rows=[];committed+=1
            print(json.dumps(dict(status='running',frames=state['frames'],chunks=len(state['chunks']),elapsedSeconds=round(attempt['wallSeconds'],2))),flush=True)

        try:
            backend=WASB(config)
            if state.get('backend') and state['backend']!=backend.provenance:
                raise ValueError('Runtime/backend changed; start a new run')
            state['backend']=backend.provenance;save(directory/'state.json',state)
            # Snapshot coverage: committing chunks must not change the decoder's resume boundary.
            origin=dict(frames=state['frames'],lastSeconds=state['lastSeconds'])
            observations=backend.observe(decoded(source['path'],origin,config['maxFrames']))
            for row in observations:
                chunk_rows.append(row)
                if len(chunk_rows)==config['chunkFrames']:
                    commit()
                    if stop_after_chunks is not None and committed>=stop_after_chunks:
                        observations.close()
                        attempt.update(status='checkpointed',wallSeconds=time.perf_counter()-started,backendMetrics=backend.metrics)
                        state['status']='checkpointed';save(directory/'state.json',state)
                        return dict(schema=SCHEMA,status='checkpointed',frames=state['frames'],runId=run_id)
            commit();unchanged(source)
            if not state['frames']:raise ValueError('Source contains no decoded frames')
            expected=video.get('nb_frames')
            if expected not in (None,'N/A') and int(expected)!=state['frames']:
                raise ValueError('Decoded coverage disagrees with source frame count')
            attempt.update(status='complete',wallSeconds=time.perf_counter()-started,backendMetrics=backend.metrics)
            result=dict(**fence,runId=run_id,status='complete',sourceProbe=probe,backend=backend.provenance,
                chunks=state['chunks'],coverage=dict(frames=state['frames'],firstSeconds=state['firstSeconds'],lastSeconds=state['lastSeconds']),
                attempts=state['attempts'],statistics=None,adjudications=[],labelsRead=False,
                limitations=['detector observations only','view candidates are not fused or adopted',
                             'frame coverage is not visible-ball recall','no point/event or winner decisions'])
            save(directory/'result.json',result)
            state.update(status='complete',resultSha256=identity(directory/'result.json')['sha256'])
            save(directory/'state.json',state)
            return result
        except BaseException as exc:
            attempt.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',
                           wallSeconds=time.perf_counter()-started,error=str(exc))
            state['status']=attempt['status'];save(directory/'state.json',state)
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source');parser.add_argument('directory');parser.add_argument('--config',required=True)
    parser.add_argument('--resume',action='store_true');parser.add_argument('--stop-after-chunks',type=int)
    args=parser.parse_args()
    result=scan(args.source,args.directory,read(args.config),args.resume,args.stop_after_chunks)
    print(json.dumps(dict(status=result['status'],coverage=result.get('coverage'),runId=result['runId']),ensure_ascii=False))


if __name__=='__main__':main()
