"""Build bounded FCP7 XMEML from an explicit edit plan; never contact Premiere.

Supports same-rate CFR cuts, full-canvas still overlays and linked source audio.
Host-dependent graphics/effects remain explicit pending operations in the report.
"""
import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path, PureWindowsPath, PurePosixPath
from urllib.parse import quote
import xml.etree.ElementTree as ET

TICKS_PER_SECOND = 254016000000
RATES = {Fraction(x) for x in ('24', '25', '30', '50', '60', '120',
                              '24000/1001', '30000/1001', '60000/1001')}


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{label} must be an integer >= {minimum}')
    return value


def rate(value):
    result = Fraction(str(value))
    if result not in RATES:
        raise ValueError('Use an explicit supported rational fps; not rounded 29.97/59.94')
    return result


def frame_ticks(frame, fps):
    value = Fraction(integer(frame, 'frame') * TICKS_PER_SECOND, 1) / rate(fps)
    if value.denominator != 1:
        raise ValueError('Frame boundary is not an integral Premiere tick')
    return str(value.numerator)


def file_uri(value):
    """Encode absolute local/UNC paths, including Unicode, spaces, # and %."""
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError('Media path must be a nonempty path without NUL')
    win = PureWindowsPath(value)
    if win.is_absolute():
        if '..' in win.parts:
            raise ValueError('Resolve parent segments in media paths first')
        if not win.drive.startswith('\\\\'):
            # Match Premiere's own FCP7 export. Pr 23.5 treats file:///C:/...
            # as a UNC-like path and opens a blocking Link Media dialog.
            return 'file://localhost/' + quote(win.as_posix(), safe='/').replace('%3A', '%3a', 1)
        return win.as_uri()
    posix = PurePosixPath(value)
    if not posix.is_absolute() or '..' in posix.parts or '://' in value:
        raise ValueError('Use an absolute local media path')
    return 'file://' + quote(posix.as_posix(), safe='/')


def sub(parent, tag, value=None, **attrs):
    node = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
    if value is not None:
        node.text = str(value)
    return node


def xml_rate(parent, fps):
    fps = rate(fps)
    node = sub(parent, 'rate')
    sub(node, 'timebase', round(fps))
    sub(node, 'ntsc', 'TRUE' if fps.denominator == 1001 else 'FALSE')


def validate(plan, check_files=False):
    if plan.get('schema') != 'tennis-edit-plan/v1' or not plan.get('revision'):
        raise ValueError('Expected tennis-edit-plan/v1 and a nonempty revision')
    if set(plan) - {'schema', 'revision', 'sequence', 'assets', 'clips', 'postImport'}:
        raise ValueError('Unsupported plan fields; use explicit postImport operations')
    seq = plan['sequence']
    if set(seq) - {'name', 'fps', 'width', 'height', 'durationFrames'}:
        raise ValueError('Unsupported sequence settings')
    if not isinstance(seq.get('name'), str) or not seq['name'].strip():
        raise ValueError('Sequence name required')
    fps = rate(seq['fps'])
    for key in ('width', 'height', 'durationFrames'):
        integer(seq[key], 'sequence.' + key, 1)
    assets = {}
    for a in plan['assets']:
        if not isinstance(a.get('id'), str) or not a['id'] or a['id'] in assets:
            raise ValueError('Missing or duplicate asset ID')
        file_uri(a['path'])
        if check_files and not Path(a['path']).is_file():
            raise ValueError('Missing media: ' + a['id'])
        if a['kind'] not in ('video', 'image'):
            raise ValueError('Only video and still-image assets supported')
        if (a['width'], a['height']) != (seq['width'], seq['height']):
            raise ValueError('This adapter requires full-canvas media; render/normalize first')
        integer(a.get('audioChannels', 0), 'audioChannels')
        if a.get('audioChannels', 0) not in (0, 1, 2):
            raise ValueError('Only no audio, mono or stereo supported')
        if a['kind'] == 'image' and a.get('audioChannels', 0):
            raise ValueError('Stills cannot carry source audio')
        if a['kind'] == 'video':
            if a.get('timing') != 'cfr' or not a.get('timingEvidence') or rate(a['fps']) != fps:
                raise ValueError('CFR at sequence fps and timingEvidence required; normalize VFR/mixed rates')
            integer(a['durationFrames'], 'asset.durationFrames', 1)
            if a.get('audioChannels', 0):
                integer(a['sampleRate'], 'sampleRate', 1)
        assets[a['id']] = a
    seen, spans, audio_spans, audio_layouts = set(), {}, {}, {}
    allowed = {'id', 'assetId', 'track', 'startFrame', 'durationFrames',
               'sourceInFrame', 'audio', 'audioTrack', 'pointId', 'reviewId',
               'name', 'sourceMapping'}
    for c in plan['clips']:
        if set(c) - allowed:
            raise ValueError('Unsupported clip fields: ' + ', '.join(sorted(set(c) - allowed)))
        if not isinstance(c.get('id'), str) or not c['id'] or c['id'] in seen:
            raise ValueError('Missing or duplicate clip ID')
        seen.add(c['id'])
        if c['assetId'] not in assets:
            raise ValueError('Unknown asset: ' + c['assetId'])
        a = assets[c['assetId']]
        start = integer(c['startFrame'], 'clip.startFrame')
        duration = integer(c['durationFrames'], 'clip.durationFrames', 1)
        track = integer(c['track'], 'clip.track', 1)
        source_in = integer(c.get('sourceInFrame', 0), 'sourceInFrame')
        if start + duration > seq['durationFrames']:
            raise ValueError('Clip beyond sequence end')
        if a['kind'] == 'video' and source_in + duration > a['durationFrames']:
            raise ValueError('Clip beyond source end')
        if a['kind'] == 'image' and source_in:
            raise ValueError('Still sourceInFrame must be zero')
        if type(c.get('audio', False)) is not bool:
            raise ValueError('audio must be boolean')
        if c.get('audio'):
            if not a.get('audioChannels'):
                raise ValueError('Requested audio is absent')
            atrack = integer(c.get('audioTrack', 1), 'audioTrack', 1)
            for channel in range(a['audioChannels']):
                layout = (a['audioChannels'], channel)
                slot = atrack + channel
                if slot in audio_layouts and audio_layouts[slot] != layout:
                    raise ValueError('Conflicting audio channel layouts; normalize or use separate audio tracks')
                audio_layouts[slot] = layout
                audio_spans.setdefault(atrack + channel, []).append((start, start + duration))
        spans.setdefault(track, []).append((start, start + duration))
    if 1 not in spans:
        raise ValueError('A base video track is required')
    for track, ranges in spans.items():
        end = 0
        for start, stop in sorted(ranges):
            if start < end:
                raise ValueError('Overlapping clips on one video track')
            if track == 1 and start != end:
                raise ValueError('Unintended base-track gap')
            end = stop
        if track == 1 and end != seq['durationFrames']:
            raise ValueError('Base track does not cover sequence end')
    for ranges in audio_spans.values():
        end = 0
        for start, stop in sorted(ranges):
            if start < end:
                raise ValueError('Overlapping linked audio channels')
            end = stop
    for op in plan.get('postImport', []):
        if not isinstance(op, dict) or not op.get('operation') or not op.get('target'):
            raise ValueError('postImport requires operation and target; never silently omit effects')
    return assets


def build(plan, check_files=False):
    assets = validate(plan, check_files)
    seq = plan['sequence']
    fps = seq['fps']
    root = ET.Element('xmeml', version='5')
    sequence = sub(root, 'sequence', id='tennis-sequence')
    sub(sequence, 'name', seq['name'])
    sub(sequence, 'duration', seq['durationFrames'])
    xml_rate(sequence, fps)
    tc = sub(sequence, 'timecode'); xml_rate(tc, fps)
    sub(tc, 'string', '00:00:00:00'); sub(tc, 'frame', 0); sub(tc, 'displayformat', 'NDF')
    media = sub(sequence, 'media'); video = sub(media, 'video')
    char = sub(sub(video, 'format'), 'samplecharacteristics')
    xml_rate(char, fps)
    sub(char, 'width', seq['width']); sub(char, 'height', seq['height'])
    sub(char, 'anamorphic', 'FALSE'); sub(char, 'pixelaspectratio', 'square')
    sub(char, 'fielddominance', 'none')
    audio = sub(media, 'audio'); sub(audio, 'numOutputChannels', 2)
    char = sub(sub(audio, 'format'), 'samplecharacteristics')
    sub(char, 'depth', 16); sub(char, 'samplerate', 48000)
    outputs = sub(audio, 'outputs')
    for channel in (1, 2):
        group = sub(outputs, 'group'); sub(group, 'index', channel)
        sub(group, 'numchannels', 1); sub(group, 'downmix', 0)
        sub(sub(group, 'channel'), 'index', channel)
    vtracks, atracks = {}, {}
    for n in range(1, max(c['track'] for c in plan['clips']) + 1):
        vtracks[n] = sub(video, 'track')
    max_audio = max((c.get('audioTrack', 1) + assets[c['assetId']]['audioChannels'] - 1
                     for c in plan['clips'] if c.get('audio')), default=0)
    audio_layouts = {}
    for c in plan['clips']:
        if c.get('audio'):
            channels = assets[c['assetId']]['audioChannels']
            for channel in range(channels):
                audio_layouts[c.get('audioTrack', 1) + channel] = (channels, channel)
    for n in range(1, max_audio + 1):
        channels, channel = audio_layouts.get(n, (1, 0))
        atracks[n] = sub(audio, 'track', currentExplodedTrackIndex=channel,
                        totalExplodedTrackCount=channels,
                        premiereTrackType='Stereo' if channels == 2 else 'Mono',
                        PannerCurrentValue='0.5', PannerName='Balance')
    file_ids = {key: 'file-' + str(i + 1) for i, key in enumerate(assets)}
    emitted = set()
    counts = {}

    def file_element(parent, a, clip_duration):
        fid = file_ids[a['id']]
        f = sub(parent, 'file', id=fid)
        if fid in emitted:
            return
        emitted.add(fid)
        sub(f, 'name', a['id']); sub(f, 'pathurl', file_uri(a['path']))
        xml_rate(f, fps)
        sub(f, 'duration', a.get('durationFrames', max(seq['durationFrames'], clip_duration)))
        fm = sub(f, 'media'); vc = sub(sub(fm, 'video'), 'samplecharacteristics')
        xml_rate(vc, fps); sub(vc, 'width', a['width']); sub(vc, 'height', a['height'])
        sub(vc, 'pixelaspectratio', 'square'); sub(vc, 'fielddominance', 'none')
        if a.get('audioChannels'):
            ac = sub(fm, 'audio'); sc = sub(ac, 'samplecharacteristics')
            sub(sc, 'depth', 16); sub(sc, 'samplerate', a['sampleRate'])
            sub(ac, 'channelcount', a['audioChannels'])

    mapping = []
    for i, c in enumerate(sorted(plan['clips'], key=lambda x: (x['startFrame'], x['track'], x['id']))):
        a = assets[c['assetId']]; duration = c['durationFrames']; source_in = c.get('sourceInFrame', 0)
        entries = [('video', c['track'], 1, 'clip-v-' + str(i + 1))]
        if c.get('audio'):
            entries += [('audio', c.get('audioTrack', 1) + ch, ch + 1, f'clip-a-{i + 1}-{ch + 1}')
                        for ch in range(a['audioChannels'])]
        indexed = []
        for kind, track, channel, cid in entries:
            counts[(kind, track)] = counts.get((kind, track), 0) + 1
            indexed.append((kind, track, channel, cid, counts[(kind, track)]))
        for kind, track, channel, cid, _ in indexed:
            node = sub((vtracks if kind == 'video' else atracks)[track], 'clipitem', id=cid)
            if kind == 'audio':
                node.set('premiereChannelType', 'stereo' if a['audioChannels'] == 2 else 'mono')
            sub(node, 'name', c.get('name', c['id']))
            sub(node, 'enabled', 'TRUE'); sub(node, 'duration', a.get('durationFrames', duration))
            xml_rate(node, fps)
            sub(node, 'start', c['startFrame']); sub(node, 'end', c['startFrame'] + duration)
            sub(node, 'in', source_in); sub(node, 'out', source_in + duration)
            if a['kind'] == 'image':
                sub(node, 'stillframe', 'TRUE')
            file_element(node, a, duration)
            source = sub(node, 'sourcetrack'); sub(source, 'mediatype', kind); sub(source, 'trackindex', channel)
            for lk, lt, _, lid, li in indexed:
                link = sub(node, 'link'); sub(link, 'linkclipref', lid)
                sub(link, 'mediatype', lk); sub(link, 'trackindex', lt); sub(link, 'clipindex', li)
                if lk == 'audio':
                    sub(link, 'groupindex', 1)
        mapping.append({**c, 'timelineStartTicks': frame_ticks(c['startFrame'], fps),
                        'timelineEndTicks': frame_ticks(c['startFrame'] + duration, fps),
                        'sourceInTicks': frame_ticks(source_in, fps)})
    for n, track in atracks.items():
        sub(track, 'enabled', 'TRUE'); sub(track, 'locked', 'FALSE')
        sub(track, 'outputchannelindex', audio_layouts.get(n, (1, 0))[1] + 1)
    ET.indent(root)
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + ET.tostring(root, encoding='unicode') + '\n'
    report = {'schema': 'tennis-premiere-exchange/v1', 'revision': plan['revision'],
              'sequence': seq, 'xmlSha256': hashlib.sha256(xml.encode()).hexdigest(),
              'assets': list(assets.values()),
              'clips': mapping, 'pendingHostOperations': plan.get('postImport', []),
              'qualification': 'generated_only; import, readback, rendered frames and audio still required'}
    return xml, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan'); parser.add_argument('output')
    parser.add_argument('--check-files', action='store_true')
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
    xml, report = build(plan, args.check_files)
    output = Path(args.output)
    report_path = output.with_suffix('.report.json')
    if output.exists() or report_path.exists():
        raise ValueError('Use a new output revision; refusing to overwrite an exchange')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep the bytes identical to xmlSha256 on Windows as well as POSIX.
    output.write_text(xml, encoding='utf-8', newline='')
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8', newline='')
    print(json.dumps({'xml': str(output), 'report': str(report_path), 'pendingHostOperations': len(report['pendingHostOperations'])}))


if __name__ == '__main__':
    main()
