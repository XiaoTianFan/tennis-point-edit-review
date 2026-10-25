"""Optional externally supplied WASB detector; observations, never match answers."""
import importlib.util
from pathlib import Path
import sys
import time

import cv2
import numpy as np

from media_probe import identity


class AttrDict(dict):
    __getattr__ = dict.__getitem__


def attributes(value):
    return AttrDict({k: attributes(v) for k, v in value.items()}) if isinstance(value, dict) else value


def configuration(value):
    allowed = {'module', 'modelConfig', 'weights', 'device', 'half', 'batch', 'threads',
               'crops', 'threshold', 'chunkFrames', 'maxFrames'}
    if set(value) - allowed:
        raise ValueError('Unknown streaming configuration fields')
    c = dict(device='cpu', half=False, batch=4, threads=4, crops=[None], threshold=.5,
             chunkFrames=1800, maxFrames=1000000)
    c.update(value)
    for key in ('module', 'modelConfig', 'weights'):
        if not isinstance(c.get(key), str) or not Path(c[key]).is_file():
            raise ValueError('Explicit external WASB '+key+' file required')
        c[key] = str(Path(c[key]).resolve())
    for key, maximum in [('batch', 16), ('threads', 32), ('chunkFrames', 30000), ('maxFrames', 10000000)]:
        if type(c[key]) is not int or not 1 <= c[key] <= maximum:
            raise ValueError('Invalid '+key)
    if c['chunkFrames'] % (3*c['batch']):
        raise ValueError('chunkFrames must be divisible by 3*batch')
    if c['device'] not in ('cpu', 'cuda') or type(c['half']) is not bool or c['half'] and c['device'] != 'cuda':
        raise ValueError('FP16 requires CUDA')
    if not isinstance(c['threshold'], (int, float)) or not 0 < c['threshold'] < 1:
        raise ValueError('Invalid detector threshold')
    if not isinstance(c['crops'], list) or not 1 <= len(c['crops']) <= 4:
        raise ValueError('Supply one to four views (null means full image)')
    for crop in c['crops']:
        if crop is not None and (not isinstance(crop, list) or len(crop) != 4 or
                any(type(v) is not int for v in crop) or min(crop[:2]) < 0 or min(crop[2:]) <= 0):
            raise ValueError('Crops must be native integer x/y/width/height rectangles')
    return c


class WASB:
    def __init__(self, config):
        import torch
        import yaml
        self.c = config
        self.torch = torch
        if config['device'] == 'cuda' and not torch.cuda.is_available():
            raise ValueError('Requested CUDA device unavailable')
        files = {k: identity(config[k]) for k in ('module', 'modelConfig', 'weights')}
        spec = importlib.util.spec_from_file_location('tennis_external_wasb', config['module'])
        module = importlib.util.module_from_spec(spec)
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = previous
        torch.set_num_threads(config['threads'])
        torch.manual_seed(0)
        if config['device'] == 'cuda':
            torch.cuda.manual_seed_all(0)
            torch.backends.cudnn.benchmark = False
        cv2.setNumThreads(1)
        cfg = attributes(yaml.safe_load(Path(config['modelConfig']).read_text(encoding='utf-8')))
        self.model = module.HRNet(cfg)
        checkpoint = torch.load(config['weights'], weights_only=True, map_location='cpu')
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.to(config['device']).eval()
        if config['half']:
            self.model.half()
        self.mean = np.array([.485, .456, .406], dtype='float32')[:, None, None]
        self.std = np.array([.229, .224, .225], dtype='float32')[:, None, None]
        self.provenance = dict(backend='external-wasb', files=files, torch=torch.__version__,
            cuda=torch.version.cuda, device=config['device'], half=config['half'],
            gpu=torch.cuda.get_device_name(0) if config['device']=='cuda' else None,
            preprocessing='RGB uniform affine 512x288; ImageNet normalization; chronological 3-in/3-out',
            scoreMeaning='uncalibrated sigmoid response; not existence probability',
            modelLicense='externally supplied; not redistributed')
        self.metrics = dict(preprocessingSeconds=0., inferenceSeconds=0., postprocessingSeconds=0.)

    def prepare(self, frame):
        started = time.perf_counter()
        image = frame.to_ndarray(format='rgb24')
        h, w = image.shape[:2]
        views = []
        for crop in self.c['crops']:
            x, y, cw, ch = crop or [0, 0, w, h]
            if x+cw>w or y+ch>h:
                raise ValueError('Crop exceeds source dimensions')
            scale = 512/max(cw, ch)
            matrix = np.float32([[scale, 0, 256-cw*scale/2], [0, scale, 144-ch*scale/2]])
            small = cv2.warpAffine(image[y:y+ch, x:x+cw], matrix, (512, 288), flags=cv2.INTER_LINEAR)
            tensor = (small.transpose(2, 0, 1).astype('float32')/255-self.mean)/self.std
            views.append(dict(input=tensor, crop=[x,y,cw,ch], scale=scale))
        self.metrics['preprocessingSeconds'] += time.perf_counter()-started
        return views

    def process(self, groups):
        torch = self.torch
        for group in groups:
            for item in group:
                if not item.get('padding'):
                    item['row']['modelCandidates'] = []
                    item['row']['views'] = []
                    item['row']['contextPts'] = [r['row']['pts'] for r in group]
                    item['row']['paddedContext'] = any(r.get('padding') for r in group)
        for vi in range(len(self.c['crops'])):
            xs = np.stack([np.concatenate([r['views'][vi]['input'] for r in group]) for group in groups])
            tensor = torch.from_numpy(xs).to(self.c['device'], dtype=torch.float16 if self.c['half'] else torch.float32)
            self.synchronize(); started = time.perf_counter()
            with torch.inference_mode():
                heat = self.model(tensor)[0].sigmoid().float().cpu().numpy()
            if heat.shape != (len(groups), 3, 288, 512):
                raise ValueError('WASB must produce three 512x288 heatmaps per input group')
            self.synchronize(); self.metrics['inferenceSeconds'] += time.perf_counter()-started
            started = time.perf_counter()
            for group, outputs in zip(groups, heat):
                for item, hm in zip(group, outputs):
                    if item.get('padding'):
                        continue
                    view = item['views'][vi]; x0,y0,cw,ch = view['crop']; scale = view['scale']
                    n, labels, _, _ = cv2.connectedComponentsWithStats((hm>self.c['threshold']).astype('uint8'))
                    if n>1025:
                        raise ValueError('Detector candidate resource limit exceeded')
                    candidates = []
                    for k in range(1,n):
                        ys,xs = np.where(labels==k); weights=hm[ys,xs]; mass=weights.sum()
                        x=(float((xs*weights).sum()/mass)-(256-cw*scale/2))/scale+x0
                        y=(float((ys*weights).sum()/mass)-(144-ch*scale/2))/scale+y0
                        # Padding responses are not source observations.
                        if not x0<=x<x0+cw or not y0<=y<y0+ch:
                            continue
                        candidates.append(dict(x=x,y=y,mass=float(mass),peak=float(weights.max()),
                                               area=int(len(xs)),view=vi))
                    candidates.sort(key=lambda c:-c['mass'])
                    item['row']['modelCandidates'].extend(candidates)
                    item['row']['views'].append(dict(crop=view['crop'],maxHeat=float(hm.max()),candidateCount=len(candidates)))
            self.metrics['postprocessingSeconds'] += time.perf_counter()-started
        return [item['row'] for group in groups for item in group if not item.get('padding')]

    def synchronize(self):
        if self.c['device']=='cuda':
            self.torch.cuda.synchronize()

    def observe(self, frames):
        """Bounded memory: at most 3*batch preprocessed frames and one native image."""
        group=[]; groups=[]
        for row, frame in frames:
            group.append(dict(row=row,views=self.prepare(frame)))
            if len(group)==3:
                groups.append(group); group=[]
                if len(groups)==self.c['batch']:
                    yield from self.process(groups); groups=[]
        if group:
            while len(group)<3:
                group.append({**group[-1], 'padding':True})
            groups.append(group)
        if groups:
            yield from self.process(groups)
