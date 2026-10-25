"""Optional source-bound body appearance observations; never player identities."""
import importlib.util
from contextlib import contextmanager
import math
from pathlib import Path
import sys
import time

from media_probe import identity


def configuration(value, player_stride):
    allowed = {'module', 'weights', 'stride', 'batchSize', 'device', 'overlayMasks'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError('Invalid appearance configuration')
    result = dict(stride=30, batchSize=16, device='cpu', overlayMasks=[])
    result.update(value)
    for key in ('module', 'weights'):
        if not isinstance(result.get(key), str) or not Path(result[key]).is_file():
            raise ValueError('Explicit external appearance '+key+' file required')
        result[key] = str(Path(result[key]).resolve())
    for key, maximum in [('stride', 600), ('batchSize', 64)]:
        if type(result[key]) is not int or not 1 <= result[key] <= maximum:
            raise ValueError('Invalid appearance '+key)
    if result['stride'] % player_stride:
        raise ValueError('Appearance stride must be a multiple of player stride')
    if result['device'] not in ('cpu', 'cuda'):
        raise ValueError('Appearance requires explicit CPU or CUDA FP32')
    masks = result['overlayMasks']
    if not isinstance(masks, list) or len(masks) > 16:
        raise ValueError('Appearance masks must be a bounded list')
    for box in masks:
        if (not isinstance(box, list) or len(box) != 4 or
                any(type(v) is not int for v in box) or min(box[:2]) < 0 or
                box[2] <= box[0] or box[3] <= box[1]):
            raise ValueError('Appearance masks require native integer XYXY rectangles')
    return result


def crop_box(box, width, height):
    if (not isinstance(box, list) or len(box) != 4 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in box)):
        raise ValueError('Appearance body box must contain four finite coordinates')
    x, y = max(0, math.floor(box[0])), max(0, math.floor(box[1]))
    right, bottom = min(width, math.ceil(box[2])), min(height, math.ceil(box[3]))
    return [x, y, right, bottom] if right > x and bottom > y else None


@contextmanager
def fp32_execution(torch, device):
    """Use full FP32 locally; preserve other models' process-wide backend flags."""
    previous = None
    if device == 'cuda':
        previous = (torch.backends.cudnn.allow_tf32, torch.backends.cuda.matmul.allow_tf32)
    try:
        if previous is not None:
            torch.backends.cudnn.allow_tf32 = False
            torch.backends.cuda.matmul.allow_tf32 = False
        with torch.inference_mode():
            yield
    finally:
        if previous is not None:
            torch.backends.cudnn.allow_tf32, torch.backends.cuda.matmul.allow_tf32 = previous


class Appearance:
    """Author OSNet-AIN architecture and pure tensor weights are supplied locally.

    The explicit external module executes Python, like the optional ball loader.
    No source, weights, account data or inferred player labels are bundled here.
    """
    def __init__(self, config):
        import torch
        import torchvision
        import PIL
        from torchvision import transforms
        from PIL import Image

        self.c = config; self.torch = torch; self.Image = Image
        if config['device'] == 'cuda' and not torch.cuda.is_available():
            raise ValueError('Appearance CUDA unavailable; select CPU explicitly')
        files = {key: identity(config[key]) for key in ('module', 'weights')}
        spec = importlib.util.spec_from_file_location('tennis_external_appearance', config['module'])
        module = importlib.util.module_from_spec(spec)
        old_bytecode = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = old_bytecode
        raw = torch.load(config['weights'], map_location='cpu', weights_only=True)
        if not isinstance(raw, dict) or not raw or any(not isinstance(k, str) or not isinstance(v, torch.Tensor) for k, v in raw.items()):
            raise ValueError('Appearance weights must be a pure tensor state dictionary')
        state = {k.removeprefix('module.'): v for k, v in raw.items()}
        classifier = state.get('classifier.weight')
        if len(state) != len(raw) or classifier is None or classifier.ndim != 2 or classifier.shape[1] != 512:
            raise ValueError('Unsupported OSNet-AIN state dictionary')
        self.model = module.osnet_ain_x1_0(num_classes=classifier.shape[0], pretrained=False)
        self.model.load_state_dict(state, strict=True)
        self.model.to(config['device']).float().eval()
        self.preprocess = transforms.Compose([
            transforms.Resize((256, 128)), transforms.ToTensor(),
            transforms.Normalize([.485, .456, .406], [.229, .224, .225])])
        self.provenance = dict(backend='external-osnet-ain-x1-0', files=files,
            torch=torch.__version__, torchvision=torchvision.__version__, pillow=PIL.__version__,
            device=config['device'], precision='float32', featureDimension=512,
            cuda=torch.version.cuda, cudnn=torch.backends.cudnn.version(),
            tf32=False, backendFlagsScope='Appearance inference only; previous flags restored',
            preprocessing='RGB native floor/ceil clipped body, PIL bilinear 256x128, ImageNet normalization',
            overlayMasks=config['overlayMasks'], embedding='L2 normalized; cosine distance is not a probability',
            strictStateKeys=len(state), implicitPretrainedDownload=False,
            interpretation='Anonymous appearance observation, not player identity, handedness or biometric identity',
            modelLicense='External author architecture and weights; review supplied artifact terms; not redistributed')
        self.metrics = dict(sampledFrames=0, crops=0, invalidCrops=0,
                            preprocessingSeconds=0., inferenceSeconds=0.)

    def annotate(self, rgb, detections):
        height, width = rgb.shape[:2]
        for box in self.c['overlayMasks']:
            if box[2] > width or box[3] > height:
                raise ValueError('Appearance overlay mask exceeds native frame')
        native = rgb.copy() if self.c['overlayMasks'] else rgb
        for x, y, right, bottom in self.c['overlayMasks']:
            native[y:bottom, x:right] = 0
        self.metrics['sampledFrames'] += 1
        queue = []; owners = []

        def flush():
            if not queue:
                return
            started = time.perf_counter()
            tensor = self.torch.stack(queue).to(self.c['device'])
            with fp32_execution(self.torch, self.c['device']):
                output = self.model(tensor)
                if (not isinstance(output, self.torch.Tensor) or
                        output.ndim != 2 or output.shape != (len(queue), 512) or
                        not self.torch.isfinite(output).all() or
                        not (self.torch.linalg.vector_norm(output, dim=1) > 1e-12).all()):
                    raise ValueError('Invalid appearance embedding output')
                features = self.torch.nn.functional.normalize(output, dim=1).cpu().numpy()
            self.metrics['inferenceSeconds'] += time.perf_counter()-started
            for detection, feature in zip(owners, features):
                detection['appearance']['embedding'] = feature.tolist()
                detection['appearance']['status'] = 'observed'
            self.metrics['crops'] += len(queue)
            queue.clear(); owners.clear()

        for detection in detections:
            started = time.perf_counter()
            box = crop_box(detection['box'], width, height)
            detection['appearance'] = dict(schema='tennis-body-appearance/v1', status='invalid_crop' if box is None else 'pending',
                cropXYXY=box, embedding=None, normalized=True, adopted=False)
            if box is None:
                self.metrics['invalidCrops'] += 1
                continue
            x, y, right, bottom = box
            queue.append(self.preprocess(self.Image.fromarray(native[y:bottom, x:right])))
            owners.append(detection)
            self.metrics['preprocessingSeconds'] += time.perf_counter()-started
            if len(queue) >= self.c['batchSize']:
                flush()
        flush()
