"""Optional vision observations. Scores are detector outputs, never probabilities of truth."""
import hashlib
import importlib.util
from pathlib import Path
import sys

import cv2
import numpy as np

from media_probe import identity

# Keypoint order of the optional external court model; far baseline is y=23.77.
COURT = np.array([[0,23.77],[10.97,23.77],[0,0],[10.97,0],
                  [1.37,23.77],[1.37,0],[9.60,23.77],[9.60,0],
                  [1.37,18.285],[9.60,18.285],[1.37,5.485],[9.60,5.485],
                  [5.485,18.285],[5.485,5.485]], np.float32)


def components(mask, strength, sx=1., sy=1., min_area=1, max_area=190, max_span=35):
    n, labels, stats, centres = cv2.connectedComponentsWithStats(mask.astype('uint8'))
    result = []
    for j in range(1, n):
        x,y,w,h,area = map(int, stats[j])
        if not min_area <= area <= max_area or max(w,h) > max_span:
            continue
        pixels = labels[y:y+h,x:x+w] == j
        score = float(strength[y:y+h,x:x+w][pixels].max())
        result.append(dict(x=float(centres[j,0]*sx), y=float(centres[j,1]*sy),
                           box=[x*sx,y*sy,w*sx,h*sy], areaPixels=area,
                           score=score, scoreKind='uncalibrated_response'))
    return sorted(result, key=lambda x:(-x['score'],x['x'],x['y']))


def classical(frame, previous, config):
    """Native/working pixel colour + motion candidates, including competing objects."""
    if previous is None:
        return []
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    colour = cv2.inRange(hsv, np.array(config['hsvLow']), np.array(config['hsvHigh']))
    diff = cv2.absdiff(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY), previous)
    mask = (colour > 0) & (diff >= config['motionThreshold'])
    return components(mask, diff, max_area=config['maxArea'], max_span=config['maxSpan'])


class LocalTrackNet:
    """Opt-in loader; no third-party source or checkpoints are shipped/downloaded.

    The caller explicitly selects a local architecture module and state_dicts.
    Importing that module executes local Python code; fingerprints are recorded.
    Only restricted weights_only state_dict deserialization is permitted.
    """
    def __init__(self, config):
        import torch
        self.torch = torch
        self.device = config.get('device', 'cpu')
        if self.device not in ('cpu','cuda') or self.device == 'cuda' and not torch.cuda.is_available():
            raise ValueError('Requested torch device unavailable')
        torch.set_num_threads(config.get('threads', 8))
        torch.manual_seed(0)
        torch.use_deterministic_algorithms(True)
        if self.device == 'cuda':
            torch.backends.cudnn.benchmark = False
        files = {k:identity(config[k]) for k in ('module','ballWeights','courtWeights')}
        spec = importlib.util.spec_from_file_location('tennis_optional_tracknet', files['module']['path'])
        module = importlib.util.module_from_spec(spec)
        previous_bytecode = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = previous_bytecode
        self.ball = module.BallTrackerNet(input_channels=9, out_channels=256)
        self.court = module.BallTrackerNet(input_channels=3, out_channels=15)
        for model, key in ((self.ball,'ballWeights'),(self.court,'courtWeights')):
            model.load_state_dict(torch.load(files[key]['path'], map_location='cpu', weights_only=True))
            model.to(self.device).eval()
        self.provenance = dict(backend='local-tracknet', files=files, torch=torch.__version__,
                               device=self.device, threads=torch.get_num_threads(),
                               inputSize=[640,360], inputOrder='BGR current,previous,previous2',
                               postprocess='ordinal heatmap >=128; connected components; no interpolation',
                               deterministicAlgorithms=True, weightLicense='external; not redistributed')

    def tensor(self, frames):
        a = np.concatenate([cv2.resize(f,(640,360),interpolation=cv2.INTER_LINEAR) for f in frames],axis=2)
        return self.torch.from_numpy(a.transpose(2,0,1).copy()[None]).to(self.device).float()/255

    def detect(self, frames):
        if len(frames) < 3:
            return []
        with self.torch.inference_mode():
            heat = self.ball(self.tensor(frames[-3:][::-1])).argmax(1)[0].cpu().numpy()
        h,w = frames[-1].shape[:2]
        # Class index represents heatmap intensity. Do not multiply uint8 by 255:
        # overflow changes the mask, unlike the intended >=128 ordinal threshold.
        return components(heat >= 128, heat, w/640, h/360, max_area=180, max_span=24)

    def court_points(self, frame):
        with self.torch.inference_mode():
            heat = self.court(self.tensor([frame]))[0].sigmoid().cpu().numpy()
        h,w = frame.shape[:2]
        points=[]
        for index, m in enumerate(heat[:14]):
            cs = components(m >= .67, m, w/640, h/360, min_area=2,max_area=3500,max_span=100)
            points.append(dict(keypoint=index, candidates=cs,
                               selected=cs[0] if len(cs)==1 else None))
        return points


def fit_court(image_points, court_points, tolerance=8):
    """Fit redundant correspondences; residual is fit consistency, not true accuracy."""
    if len(image_points) < 6 or len(image_points) != len(court_points):
        return dict(status='abstained', reason='need_at_least_six_correspondences')
    img=np.asarray(image_points,dtype=np.float32); ground=np.asarray(court_points,dtype=np.float32)
    if not np.isfinite(img).all() or not np.isfinite(ground).all():
        raise ValueError('Nonfinite court anchors')
    cv2.setRNGSeed(0)
    reverse,inliers=cv2.findHomography(ground,img,cv2.RANSAC,tolerance)
    if reverse is None or inliers is None or int(inliers.sum()) < 6:
        return dict(status='abstained',reason='insufficient_consistent_court_points')
    projected=cv2.perspectiveTransform(ground[None],reverse)[0]
    residual=np.linalg.norm(projected-img,axis=1)
    good=inliers.ravel().astype(bool)
    # A fit must not quietly discard a whole contradictory court side. RANSAC
    # support alone can produce a plausible but spatially wrong ground map.
    if good.sum()/len(img)<.75 or np.max(residual[good])>tolerance or np.max(residual)>3*tolerance or abs(np.linalg.det(reverse))<1e-10:
        return dict(status='abstained',reason='court_geometry_inconsistent',residualPixels=residual.tolist())
    return dict(status='candidate',imageToGround=np.linalg.inv(reverse).tolist(),
                groundToImage=reverse.tolist(),inliers=good.tolist(),residualPixels=residual.tolist(),
                residualMeaning='fit consistency only; not independently validated accuracy',
                coordinates='metres; doubles far-left=(0,23.77), near-left=(0,0)',
                projectionUse='conditional ground-contact hypotheses only')


def ground_hypothesis(court, xy, pixel_radius):
    if court.get('status') != 'candidate':
        return None
    points=np.asarray([[xy[0]+dx,xy[1]+dy] for dx,dy in
                       [(0,0),(-pixel_radius,0),(pixel_radius,0),(0,-pixel_radius),(0,pixel_radius)]],np.float32)
    projected=cv2.perspectiveTransform(points[None],np.asarray(court['imageToGround']))[0]
    if not np.isfinite(projected).all() or np.max(np.abs(projected))>100:
        return None
    return dict(x=float(projected[0,0]),y=float(projected[0,1]),
                sensitivityBounds=[projected.min(0).tolist(),projected.max(0).tolist()],
                pixelPerturbation=pixel_radius,
                meaning='IF this pixel is ground contact; sensitivity only, not confidence interval; excludes calibration/lens error')


def camera_change(reference, current):
    """Global affine feature displacement from the window anchor; unknown fails closed."""
    corners=cv2.goodFeaturesToTrack(reference,maxCorners=180,qualityLevel=.02,minDistance=12)
    if corners is None or len(corners)<12:
        return dict(status='unknown',reason='insufficient_background_features')
    q,ok,_=cv2.calcOpticalFlowPyrLK(reference,current,corners,None)
    if q is None or ok is None or int(ok.sum())<12:
        return dict(status='unknown',reason='background_flow_failed')
    a=corners[ok.ravel()==1];b=q[ok.ravel()==1]
    transform,inliers=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=2)
    if transform is None or inliers is None or int(inliers.sum())<12:
        return dict(status='unknown',reason='background_registration_failed')
    h,w=reference.shape
    box=np.array([[0,0,1],[w,0,1],[0,h,1],[w,h,1]],float)
    displacement=float(np.linalg.norm(box@transform.T-box[:,:2],axis=1).max())
    return dict(status='stable_candidate' if displacement<2 else 'moving',
                maxDisplacementAnalysisPixels=displacement,inliers=int(inliers.sum()))


def select_track(candidates, previous, dt, diagonal):
    if not candidates:
        return None,'no_detection'
    if previous is None:
        return (candidates[0],'single_candidate') if len(candidates)==1 else (None,'multiple_candidates')
    nearby=[c for c in candidates if np.hypot(c['x']-previous['x'],c['y']-previous['y']) <= diagonal*3*dt]
    return (nearby[0],'temporal_gate') if len(nearby)==1 else (None,'ambiguous_or_jump')
