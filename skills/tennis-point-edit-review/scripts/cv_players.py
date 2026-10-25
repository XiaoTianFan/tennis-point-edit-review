"""Optional external person/pose observations; no identity or tennis decisions."""
import json
import math
import os
from pathlib import Path
import time

import cv2
import numpy as np

from media_probe import identity

KEYPOINTS = ['nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
             'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
             'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
             'left_knee', 'right_knee', 'left_ankle', 'right_ankle']


def configuration(value):
    if not isinstance(value, dict):
        raise ValueError('players must be an explicit configuration object')
    allowed = {'weights', 'architecture', 'stride', 'inputSize', 'threshold',
               'nmsIoU', 'maxDetections', 'crops', 'device', 'half'}
    if set(value) - allowed:
        raise ValueError('Unknown player observation configuration fields')
    c = dict(stride=6, inputSize=640, threshold=.15, nmsIoU=.7,
             maxDetections=32, crops=[None], device='cpu', half=False)
    c.update(value)
    for name in ('weights', 'architecture'):
        if not isinstance(c.get(name), str) or not Path(c[name]).is_file():
            raise ValueError('Explicit external player '+name+' file required')
        c[name] = str(Path(c[name]).resolve())
    for name, maximum in [('stride', 600), ('inputSize', 1920), ('maxDetections', 128)]:
        if type(c[name]) is not int or not 1 <= c[name] <= maximum:
            raise ValueError('Invalid player '+name)
    if c['inputSize'] < 32 or c['inputSize'] % 32:
        raise ValueError('Player inputSize must be a multiple of 32')
    for name in ('threshold', 'nmsIoU'):
        if type(c[name]) not in (int, float) or not math.isfinite(c[name]) or not 0 < c[name] < 1:
            raise ValueError('Invalid player '+name)
    if c['device'] not in ('cpu', 'cuda') or type(c['half']) is not bool or c['half'] and c['device'] != 'cuda':
        raise ValueError('Player FP16 requires CUDA; select CPU FP32 explicitly')
    if not isinstance(c['crops'], list) or not 1 <= len(c['crops']) <= 4:
        raise ValueError('Supply one to four player views')
    for crop in c['crops']:
        if crop is not None and (not isinstance(crop, list) or len(crop) != 4 or
                any(type(v) is not int for v in crop) or min(crop[:2]) < 0 or min(crop[2:]) <= 0):
            raise ValueError('Player crops must be native integer rectangles')
    return c


class SharedFrame:
    """One decoded frame, one cached RGB conversion, released with this frame."""
    def __init__(self, frame):
        self.frame = frame
        self.rgb = None

    def __getattr__(self, name):
        return getattr(self.frame, name)

    def to_ndarray(self, *, format):
        if format != 'rgb24':
            return self.frame.to_ndarray(format=format)
        if self.rgb is None:
            self.rgb = self.frame.to_ndarray(format=format)
        return self.rgb


class Players:
    def __init__(self, config, cache_directory):
        # External Ultralytics is optional and never installed or downloaded here.
        # A new process/run uses a local settings directory, not a global service.
        cache_directory = Path(cache_directory).resolve()
        cache_directory.mkdir(parents=True, exist_ok=True)
        os.environ['YOLO_CONFIG_DIR'] = str(cache_directory)
        os.environ['YOLO_OFFLINE'] = 'true'
        os.environ['YOLO_AUTOINSTALL'] = 'false'
        import torch
        import ultralytics
        from ultralytics import utils as external_utils
        from ultralytics.nn.tasks import PoseModel
        from torchvision.ops import nms
        if external_utils.USER_CONFIG_DIR.resolve() != cache_directory/'Ultralytics' or external_utils.ONLINE:
            raise ValueError('Player backend requires a fresh process with the isolated offline settings directory')
        external_utils.SETTINGS.update(sync=False, hub=False,
            datasets_dir=str(cache_directory/'datasets'), weights_dir=str(cache_directory/'weights'),
            runs_dir=str(cache_directory/'runs'))
        self.c = config; self.torch = torch; self.nms = nms
        if config['device'] == 'cuda' and not torch.cuda.is_available():
            raise ValueError('Requested player CUDA device unavailable; select CPU explicitly')
        files = {k: identity(config[k]) for k in ('weights', 'architecture')}
        meta = json.loads(Path(config['architecture']).read_text(encoding='utf-8'))
        if meta.get('stateSha256') != files['weights']['sha256'] or not isinstance(meta.get('architecture'), dict):
            raise ValueError('Player architecture metadata does not bind these pure-state weights')
        self.model = PoseModel(meta['architecture'], ch=3, nc=1, data_kpt_shape=(17,3), verbose=False)
        self.model.load_state_dict(torch.load(config['weights'], weights_only=True, map_location='cpu'))
        self.model.to(config['device']).eval()
        if config['half']:
            self.model.half()
        self.provenance = dict(backend='external-ultralytics-pose', files=files,
            ultralytics=ultralytics.__version__, torch=torch.__version__,
            implementation=identity(Path(ultralytics.__file__).parent/'nn/tasks.py'),
            device=config['device'], half=config['half'], keypointNames=KEYPOINTS,
            preprocessing='RGB letterbox, stride32 padding114, zero-to-one channels',
            scoreMeaning='uncalibrated detector/keypoint responses',
            modelLicense='external dependency and weights; not redistributed; review upstream terms')
        self.metrics = dict(sampledFrames=0, detections=0, preprocessingSeconds=0.,
                            inferenceSeconds=0., postprocessingSeconds=0.)

    def detect(self, rgb, crop, view, frame_id):
        torch = self.torch; started = time.perf_counter()
        height, width = rgb.shape[:2]
        x, y, cw, ch = crop or [0, 0, width, height]
        if x+cw > width or y+ch > height:
            raise ValueError('Player crop exceeds source dimensions')
        size = self.c['inputSize']; scale = min(size/cw, size/ch)
        rw, rh = max(1, round(cw*scale)), max(1, round(ch*scale))
        dw, dh = (size-rw) % 32, (size-rh) % 32
        left, top = round(dw/2-.1), round(dh/2-.1)
        image = cv2.copyMakeBorder(cv2.resize(rgb[y:y+ch,x:x+cw], (rw,rh)),
            top, round(dh/2+.1), left, round(dw/2+.1), cv2.BORDER_CONSTANT, value=(114,114,114))
        tensor = torch.from_numpy(image.transpose(2,0,1).copy()[None]).to(self.c['device'])
        tensor = (tensor.half() if self.c['half'] else tensor.float())/255
        self.metrics['preprocessingSeconds'] += time.perf_counter()-started
        started = time.perf_counter()
        with torch.inference_mode():
            pred = self.model(tensor)[0][0].T.float()
        if self.c['device'] == 'cuda':
            torch.cuda.synchronize()
        self.metrics['inferenceSeconds'] += time.perf_counter()-started
        started = time.perf_counter()
        if pred.ndim != 2 or pred.shape[1] != 56 or not torch.isfinite(pred).all():
            raise ValueError('Unsupported or nonfinite player pose output')
        pred = pred[pred[:,4] >= self.c['threshold']]
        boxes = pred[:,:4].clone()
        boxes[:,:2] = pred[:,:2]-pred[:,2:4]/2
        boxes[:,2:] = pred[:,:2]+pred[:,2:4]/2
        kept = self.nms(boxes, pred[:,4], self.c['nmsIoU'])
        truncated_count = max(0, len(kept)-self.c['maxDetections'])
        detections = []
        for order, idx in enumerate(kept[:self.c['maxDetections']]):
            box = boxes[idx].clone()
            box[[0,2]] = (box[[0,2]]-left)/scale+x
            box[[1,3]] = (box[[1,3]]-top)/scale+y
            keypoints = pred[idx,5:].reshape(17,3).clone()
            keypoints[:,0] = (keypoints[:,0]-left)/scale+x
            keypoints[:,1] = (keypoints[:,1]-top)/scale+y
            b = box.cpu().tolist()
            clipped = b[0] < x+2 or b[1] < y+2 or b[2] > x+cw-2 or b[3] > y+ch-2
            detections.append(dict(id=f'{frame_id}:V{view}:D{order}', box=b,
                response=float(pred[idx,4]), keypoints=keypoints.cpu().tolist(),
                view=view, crop=[x,y,cw,ch], truncatedByView=clipped,
                playerId=None, handedness='unknown', side='unknown', trackId=None))
        self.metrics['postprocessingSeconds'] += time.perf_counter()-started
        return detections, truncated_count

    def annotate(self, frames):
        for row, frame in frames:
            observation = dict(schema='tennis-player-frame/v1', sampled=False,
                detections=[], views=[], associations=[], motions=[], adjudication=None)
            row['playerObservations'] = observation
            if int(row['id'][1:]) % self.c['stride'] == 0:
                frame = SharedFrame(frame); rgb = frame.to_ndarray(format='rgb24')
                observation['sampled'] = True
                for view, crop in enumerate(self.c['crops']):
                    detections, dropped = self.detect(rgb, crop, view, row['id'])
                    observation['detections'].extend(detections)
                    observation['views'].append(dict(view=view, crop=crop, omittedByResourceLimit=dropped))
                self.metrics['sampledFrames'] += 1
                self.metrics['detections'] += len(observation['detections'])
            yield row, frame
