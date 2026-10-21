"""Original identity and presentation-clock contracts, independent of review proxies."""
from fractions import Fraction
from pathlib import Path
from media_probe import identity, metadata

MAPPING = 'original-pts-grid/v1'


def mapping(info, start=0):
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    origin = Fraction(info.get('format', {}).get('start_time', '0')) + Fraction(str(start))
    return dict(schema=MAPPING, originSeconds=str(origin), containerStartSeconds=info.get('format', {}).get('start_time', '0'), timeBase=video['time_base'],
                firstPts=video.get('start_pts'), resampling='fps-round-near')


def verify_original(asset):
    path = asset.get('originalPath')
    expected = asset.get('sourceIdentity', {})
    clock = asset.get('sourceMapping', {})
    if not path or not Path(path).is_file():
        raise ValueError('Original unavailable: ' + str(path or asset.get('id')))
    if not expected.get('sha256') or clock.get('schema') != MAPPING:
        raise ValueError('Unbound original: prepare new media or explicitly bind-sources after checking the legacy mapping')
    current = identity(path)
    if any(current[k] != expected.get(k) for k in ('size', 'sha256')):
        raise ValueError('Original identity mismatch: ' + str(path))
    info=metadata(path)
    video=next(s for s in info['streams'] if s['codec_type']=='video')
    if video.get('color_transfer') in ('smpte2084','arib-std-b67'):
        raise ValueError('HDR original requires an explicitly verified transform')
    declared=mapping(info,asset.get('sourceStartSeconds',0))
    if any(clock.get(k)!=declared[k] for k in ('timeBase','firstPts','originSeconds','containerStartSeconds','resampling')):
        raise ValueError('Original timing mapping mismatch; reconcile source and cuts')
    return current


def unchanged(fingerprint):
    stat = Path(fingerprint['path']).stat()
    if (stat.st_size, stat.st_mtime_ns) != (fingerprint['size'], fingerprint['mtimeNs']):
        raise ValueError('Original changed during processing')


def bind_legacy(asset):
    """Explicit owner acceptance of CURRENT bytes; never certify historical identity.

    Only the old zero-origin full-source grid is unambiguous. Bounded/nonzero
    proxies must be prepared again and their cuts reviewed, not silently shifted.
    """
    path = asset.get('originalPath')
    if not path or not Path(path).is_file():
        raise ValueError('Original unavailable for binding')
    old = asset.get('sourceProbe')
    if not old:
        raise ValueError('Legacy sourceProbe missing; prepare media and reconcile cuts')
    current = metadata(path)
    before = next(s for s in old['streams'] if s['codec_type'] == 'video')
    after = next(s for s in current['streams'] if s['codec_type'] == 'video')
    keys = ('codec_name', 'width', 'height', 'time_base', 'start_pts', 'duration_ts', 'r_frame_rate')
    if any(before.get(k) != after.get(k) for k in keys):
        raise ValueError('Legacy source metadata changed; reconcile source and cuts')
    proxy = metadata(asset['path'])
    pv = next(s for s in proxy['streams'] if s['codec_type'] == 'video')
    if (Fraction(str(asset.get('sourceStartSeconds', 0))) != 0 or
            Fraction(current.get('format', {}).get('start_time', '0')) != 0 or
            int(pv.get('start_pts', -1)) != 0):
        raise ValueError('Ambiguous legacy grid origin; prepare media again and reconcile cuts')
    return {**asset, 'sourceIdentity': identity(path), 'sourceMapping': mapping(current),
            'binding': 'owner-accepted-current-bytes; historical identity not established'}
