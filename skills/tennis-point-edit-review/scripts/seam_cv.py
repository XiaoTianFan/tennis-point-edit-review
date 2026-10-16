"""Spatially local, motion-compensated seam evidence for fixed-court edits.

Every frame is decoded. Local tile changes avoid dilution by a static court;
bidirectional flow residual and temporal innovation qualify those changes.
These are review candidates, never automatic tennis/outcome decisions.
"""
from collections import deque
import csv
from pathlib import Path
import subprocess


def local_score(image, np):
    # Mean of the four strongest non-overlapping tiles (not a single noisy pixel).
    h, w = image.shape
    tiles = image[:h//12*12, :w//16*16].reshape(h//12, 12, w//16, 16).mean(axis=(1, 3)).ravel()
    return float(np.sort(tiles)[-4:].mean()) * 100 / 255


def scan_local(source, directory, width, expected, window=30):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise ValueError('Seam CV requires numpy and opencv-python; install in the task runtime, then rerun') from exc
    cv2.setNumThreads(1)
    # FFmpeg keeps display order; the primary scan supplies the verified PTS map.
    info = __import__('media_probe').metadata(source)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    height = max(24, round(int(video['height']) * width / int(video['width']) / 2) * 2)
    command = ['ffmpeg', '-v', 'error', '-nostdin', '-xerror', '-i', str(source), '-map', '0:v:0',
               '-vf', f'scale={width}:{height}:flags=area,format=gray', '-fps_mode', 'passthrough',
               '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    directory = Path(directory)
    previous = older = None
    history = deque(maxlen=window)
    rows, candidates = [], []
    yy, xx = np.mgrid[:height, :width].astype(np.float32)
    flow_engine = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST)
    with (directory/'cv-decode.log').open('wb') as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            while True:
                data = process.stdout.read(width*height)
                if not data:
                    break
                if len(data) != width*height:
                    raise ValueError('Incomplete CV decoded frame')
                current = np.frombuffer(data, np.uint8).reshape(height, width).copy()
                row = dict(frame=len(rows), localDifference=0., innovation=0., motionResidual=0.)
                if previous is not None:
                    difference = cv2.absdiff(current, previous)
                    score = local_score(difference, np)
                    row['localDifference'] = score
                    baseline = float(np.median(history)) if history else 0.
                    mad = float(np.median(np.abs(np.array(history)-baseline))) if history else 0.
                    threshold = max(1.5, baseline*2.2, baseline+7*mad)
                    if older is not None:
                        predicted = np.clip(previous.astype(np.int16)*2-older, 0, 255).astype(np.uint8)
                        row['innovation'] = local_score(cv2.absdiff(current, predicted), np)
                    if score >= threshold:
                        # Warp both ways: ordinary translation should explain itself;
                        # a cut can replace/disocclude foreground and resists both fits.
                        back = flow_engine.calc(current, previous, None)
                        forward = flow_engine.calc(previous, current, None)
                        a = cv2.remap(previous, xx+back[:,:,0], yy+back[:,:,1], cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_REPLICATE)
                        b = cv2.remap(current, xx+forward[:,:,0], yy+forward[:,:,1], cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_REPLICATE)
                        residual = min(local_score(cv2.absdiff(current,a),np), local_score(cv2.absdiff(previous,b),np))
                        row['motionResidual'] = residual
                        if residual >= 1.2 and (older is None or row['innovation'] >= max(1.5,baseline*2)):
                            candidates.append(dict(frame=row['frame'], signals=['local_change','motion_residual'],
                                                   localThreshold=round(threshold,6), **{k:round(v,6) for k,v in row.items() if k!='frame'}))
                    history.append(score)
                rows.append(row)
                older, previous = previous.astype(np.int16) if previous is not None else None, current
        finally:
            process.stdout.close()
            if process.poll() is None and len(rows) != expected:
                process.kill()
            code = process.wait()
        if code or len(rows) != expected:
            raise ValueError(f'CV decode incomplete: {len(rows)}/{expected}, exit {code}')
    with (directory/'cv-metrics.csv').open('w',newline='',encoding='utf-8') as out:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return candidates, dict(opencv=cv2.__version__,numpy=np.__version__,decodedFrames=len(rows),
                            width=width,height=height,method='tile-local innovation + bidirectional DIS flow residual')
