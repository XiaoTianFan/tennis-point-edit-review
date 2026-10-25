"""Compare visible positive spot labels with vision output; never promote labels to truth."""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import statistics

from local_model import read, write
from media_probe import identity
from cv_pipeline import SCHEMA


def compare(run_path, reference, tolerances=(5,10,15)):
    run_path=Path(run_path);run=read(run_path)
    if run.get('schema')!=SCHEMA or run.get('status')!='complete':raise ValueError('Completed vision run required')
    if reference.get('sourceIdentity',{}).get('sha256')!=run['sourceIdentity']['sha256']:
        raise ValueError('Reference and observation source identities differ')
    if not reference.get('referenceKind'):raise ValueError('Declare reference provenance')
    observations=run_path.with_name('observations.jsonl')
    if identity(observations)['sha256']!=run['observationsSha256']:raise ValueError('Observation records changed')
    rows=[json.loads(l) for l in observations.read_text(encoding='utf-8').splitlines()]
    indexed={Fraction(r['seconds']):r for r in rows}
    results=[]
    for p in reference['points']:
        t=Fraction(p['pts'])*Fraction(p['timeBase']);row=indexed.get(t)
        if row is None:
            results.append(dict(pts=p['pts'],status='outside_observed_pts',nearestCandidateError=None,selectedError=None));continue
        candidates=row['modelCandidates'] if run['backend']['backend']=='local-tracknet' else row['colourCandidates']
        error=lambda x:math.hypot(x['x']-p['x'],x['y']-p['y'])
        results.append(dict(pts=p['pts'],status='evaluated',nearestCandidateError=min(map(error,candidates)) if candidates else None,
                            selectedError=error(row['track']) if row['track'] else None))
    summary={}
    for key in ('nearestCandidateError','selectedError'):
        measured=[p[key] for p in results if p[key] is not None]
        summary[key]=dict(measured=len(measured),nullCount=len(results)-len(measured),
                          medianPixels=statistics.median(measured) if measured else None,
                          maxPixels=max(measured) if measured else None,
                          withinPixels={str(t):sum(e<=t for e in measured) for t in tolerances})
    return dict(schema='tennis-vision-comparison/v1',referenceKind=reference['referenceKind'],referenceCount=len(results),
                referenceIdentity=reference['sourceIdentity'],runId=run['runId'],summary=summary,rows=results,
                limitations=['positive-only nonblind spot labels: not overall precision/recall',
                'nearest-candidate score is optimistic and distinct from chosen-track score',
                'null is abstention/unmapped, never zero error',
                'pixel distance only; no conversion to physical accuracy'],runtimeMetrics=run['metrics'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('result');p.add_argument('reference');p.add_argument('output');a=p.parse_args()
    if Path(a.output).exists():raise ValueError('Use a new comparison output')
    result=compare(a.result,read(a.reference));write(a.output,result);print(json.dumps(result['summary']))


if __name__=='__main__':main()
