"""Bounded, detection-free contact sheets for agent inspection of any footage."""
import argparse
import json
import math
from pathlib import Path

from media_probe import identity
from stage_cache import Stage, safe


def sample(source, start, end, output, step=5, roi=None, width=480, columns=3, page_size=12, purpose='navigation', job=None):
    import cv2
    import numpy as np
    if purpose not in ('navigation','movement','stroke','boundary'):
        raise ValueError('Precision questions require precision_evidence with native original PTS/ROI')
    if not all(math.isfinite(v) for v in (start, end, step)) or not 0 <= start < end or step <= 0:
        raise ValueError('Finite positive window and step required')
    if width < 64 or width > 1920 or not 1 <= columns <= 6 or not 1 <= page_size <= 48:
        raise ValueError('Use width 64–1920, columns 1–6 and page size 1–48')
    count = math.ceil((end-start)/step)
    if count > 2000:
        raise ValueError('Split into batches of at most 2000 requested samples')
    out = safe(output)
    out.mkdir(parents=True, exist_ok=False)
    job=safe(job) if job else out
    if not out.is_relative_to(job): raise ValueError('Catalog must be inside the declared job')
    stage = Stage.create(job,purpose)
    def put_image(name, pixels):
        ok,data=cv2.imencode(Path(name).suffix,pixels)
        if not ok: raise ValueError('Cannot encode inspection image')
        return stage.put(name,data.tobytes())
    def reference(name): return str(stage.root/'data'/name)
    fingerprint = identity(source)
    cap = cv2.VideoCapture(fingerprint['path'])
    if not cap.isOpened():
        raise ValueError('Cannot open source')
    records, sheets, page = [], [], []
    previous = -1

    def save_page():
        if not page:
            return
        height = max(tile.shape[0] for tile in page)
        canvas = np.full((math.ceil(len(page)/columns)*height, columns*width, 3), 240, np.uint8)
        for i, tile in enumerate(page):
            y, x = i//columns*height, i%columns*width
            canvas[y:y+tile.shape[0], x:x+width] = tile
        name = f'sheet-{len(sheets):04d}.jpg'
        sheets.append(put_image(name,canvas))
        page.clear()

    try:
        for i in range(count):
            requested = start + i*step
            cap.set(cv2.CAP_PROP_POS_MSEC, requested*1000)
            ok, frame = cap.read()
            record = {'requestedSeconds': requested, 'status': 'decode_failed'}
            records.append(record)
            if not ok:
                continue
            actual = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            index = round(cap.get(cv2.CAP_PROP_POS_FRAMES))-1
            if not math.isfinite(actual) or actual <= previous or not start <= actual < end:
                record.update(status='timestamp_unusable', decodedSeconds=actual if math.isfinite(actual) else None)
                continue
            previous = actual
            h, w = frame.shape[:2]
            x, y, rw, rh = roi if roi else (0, 0, w, h)
            if x < 0 or y < 0 or rw <= 0 or rh <= 0 or x+rw > w or y+rh > h:
                raise ValueError('ROI outside source frame')
            if rh*width/rw > 2160:
                raise ValueError('Contact-sheet tile too tall; use a wider ROI or smaller width')
            name = f'{i:05d}-raw.png'
            raw=put_image(name,frame)
            image = frame[y:y+rh, x:x+rw]
            small = cv2.resize(image, (width, max(1, round(rh*width/rw))))
            bar = np.full((42, width, 3), 240, np.uint8)
            cv2.putText(bar, f'{actual:.6f}s | frame {index}', (6, 16), cv2.FONT_HERSHEY_SIMPLEX, .42, (20,20,20), 1)
            cv2.putText(bar, f'request {requested:.3f}s | raw {i:05d}', (6, 34), cv2.FONT_HERSHEY_SIMPLEX, .42, (20,20,20), 1)
            record.update(status='extracted', decodedSeconds=actual, decoderFrameIndex=index,
                          seekErrorSeconds=actual-requested, raw=raw, sheet=reference(f'sheet-{len(sheets):04d}.jpg'),
                          sourceSize=[w,h], crop=[x,y,rw,rh], tileSize=[width,small.shape[0]])
            page.append(np.vstack([small,bar]))
            if len(page) == page_size:
                save_page()
        save_page()
    finally:
        cap.release()
    stat = Path(fingerprint['path']).stat()
    if (stat.st_size, stat.st_mtime_ns) != (fingerprint['size'], fingerprint['mtimeNs']):
        raise ValueError('Source changed during extraction')
    manifest = {'schema': 'tennis-source-samples/v2', 'source': fingerprint, 'stageId':stage.owner['stageId'],
                'purpose':purpose,'precisionSuitable':False,
                'windowSeconds': [start,end], 'stepSeconds': step, 'roi': roi,
                'timestampSource': 'decoder POS_MSEC; verify source PTS before precise event timing',
                'inspection': 'sampled_only', 'visualReview': 'not_performed',
                'records': records, 'sheets': sheets}
    (out/'samples.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    stage.index(out/'samples.json')
    if not sheets:
        raise ValueError('No usable samples; see samples.json, use a PTS-aware decoder')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('start', type=float); parser.add_argument('end', type=float)
    parser.add_argument('output'); parser.add_argument('--step', type=float, default=5)
    parser.add_argument('--roi', help='x,y,width,height; full original frames are always retained')
    parser.add_argument('--width', type=int, default=480)
    parser.add_argument('--columns', type=int, default=3); parser.add_argument('--page-size', type=int, default=12)
    parser.add_argument('--purpose',choices=('navigation','movement','stroke','boundary'),default='navigation')
    parser.add_argument('--job',required=True,help='Full job root containing canonical records and output')
    args = parser.parse_args()
    result = sample(args.source, args.start, args.end, args.output, args.step,
                    list(map(int, args.roi.split(','))) if args.roi else None,
                    args.width, args.columns, args.page_size,args.purpose,args.job)
    print(json.dumps({'samples': len(result['records']), 'sheets': len(result['sheets']), 'output': args.output,
                      'stage':str(Path(args.job).resolve()/'.stage-cache'/result['stageId'])}))
