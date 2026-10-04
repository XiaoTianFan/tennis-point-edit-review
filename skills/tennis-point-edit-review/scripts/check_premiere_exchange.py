"""Interchange invariants, not a claim of host import compatibility."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from premiere_exchange import build, file_uri, frame_ticks, validate


def fixture():
    return {'schema': 'tennis-edit-plan/v1', 'revision': 'synthetic-1',
            'sequence': {'name': 'Synthetic cut', 'fps': '30', 'width': 1920, 'height': 1080, 'durationFrames': 90},
            'assets': [{'id': 'source', 'path': '/media/synthetic & court.mov', 'kind': 'video',
                        'fps': '30', 'width': 1920, 'height': 1080, 'durationFrames': 300,
                        'timing': 'cfr', 'timingEvidence': 'synthetic test pattern', 'audioChannels': 2, 'sampleRate': 48000},
                       {'id': 'panel', 'path': '/media/overlay.png', 'kind': 'image', 'width': 1920, 'height': 1080}],
            'clips': [{'id': 'P001-a', 'pointId': 'P001', 'assetId': 'source', 'track': 1,
                       'startFrame': 0, 'durationFrames': 60, 'sourceInFrame': 15, 'audio': True},
                      {'id': 'P001-b', 'pointId': 'P001', 'assetId': 'source', 'track': 1,
                       'startFrame': 60, 'durationFrames': 30, 'sourceInFrame': 150, 'audio': True},
                      {'id': 'R001', 'reviewId': 'R001', 'pointId': 'P001', 'assetId': 'panel',
                       'track': 2, 'startFrame': 5, 'durationFrames': 80}]}


class ExchangeChecks(unittest.TestCase):
    def test_cli_checksum_matches_exported_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / 'plan.json'
            plan_path.write_text(json.dumps(fixture()), encoding='utf-8')
            output = root / 'cut.xml'
            subprocess.run([sys.executable, str(Path(__file__).with_name('premiere_exchange.py')),
                            str(plan_path), str(output)], check=True, capture_output=True)
            report = json.loads(output.with_suffix('.report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['xmlSha256'], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertNotIn(b'\r\n', output.read_bytes())

    def test_deterministic_no_input_mutation(self):
        p = fixture(); before = copy.deepcopy(p)
        self.assertEqual(build(p), build(p)); self.assertEqual(p, before)

    def test_linked_channels_and_half_open_cuts(self):
        xml, report = build(fixture()); root = ET.fromstring(xml)
        video = root.findall('./sequence/media/video/track/clipitem')
        self.assertEqual([(v.findtext('start'), v.findtext('end')) for v in video], [('0', '60'), ('60', '90'), ('5', '85')])
        audio = root.findall('./sequence/media/audio/track/clipitem')
        self.assertEqual(len(audio), 4)
        self.assertEqual([v.findtext('in') for v in audio], ['15', '150', '15', '150'])
        ids = {v.attrib['id'] for v in video + audio}
        self.assertTrue(all(l.text in ids for l in root.findall('.//linkclipref')))
        self.assertEqual(len(root.findall('.//file/pathurl')), 2)
        self.assertEqual(report['clips'][0]['pointId'], 'P001')

    def test_exact_ntsc_ticks_and_rate(self):
        self.assertEqual(frame_ticks(30000, '30000/1001'), str(1001 * 254016000000))
        p = fixture(); p['sequence']['fps'] = p['assets'][0]['fps'] = '30000/1001'
        root = ET.fromstring(build(p)[0])
        self.assertEqual(root.findtext('./sequence/rate/ntsc'), 'TRUE')
        self.assertEqual(root.findtext('./sequence/rate/timebase'), '30')
        with self.assertRaises(ValueError): frame_ticks(1, '29.97')

    def test_paths_unicode_reserved_and_unc(self):
        self.assertEqual(file_uri('C:\\素材\\甲 #1%.mov'), 'file:///C:/%E7%B4%A0%E6%9D%90/%E7%94%B2%20%231%25.mov')
        self.assertEqual(file_uri('\\\\server\\share\\a b.mov'), 'file://server/share/a%20b.mov')
        for value in ('relative.mov', 'https://example.com/a.mov', '/media/../a.mov', 'C:\\a\\..\\b.mov'):
            with self.assertRaises(ValueError): file_uri(value)

    def test_gaps_overlaps_and_bounds(self):
        for key, value in [('startFrame', 61), ('startFrame', 59), ('durationFrames', 31), ('sourceInFrame', 295)]:
            p = fixture(); p['clips'][1][key] = value
            with self.assertRaises(ValueError): validate(p)
        p = fixture(); p['sequence']['durationFrames'] = 91
        with self.assertRaises(ValueError): validate(p)

    def test_vfr_mixed_rate_and_unsupported_effects_rejected(self):
        for key, value in [('timing', 'vfr'), ('fps', '60'), ('timingEvidence', ''), ('audioChannels', 6)]:
            p = fixture(); p['assets'][0][key] = value
            with self.assertRaises(ValueError): validate(p)
        for key, value in [('playbackRate', 2), ('opacity', .5), ('effects', ['test'])]:
            p = fixture(); p['clips'][0][key] = value
            with self.assertRaises(ValueError): validate(p)

    def test_ids_integral_frames_and_audio(self):
        p = fixture(); p['clips'][1]['id'] = p['clips'][0]['id']
        with self.assertRaises(ValueError): validate(p)
        p = fixture(); p['clips'][0]['startFrame'] = True
        with self.assertRaises(ValueError): validate(p)
        p = fixture(); p['clips'][0]['durationFrames'] = 59.9
        with self.assertRaises(ValueError): validate(p)
        p = fixture(); p['clips'][2]['audio'] = True
        with self.assertRaises(ValueError): validate(p)

    def test_host_operations_are_explicit_and_preserved(self):
        p = fixture(); p['postImport'] = [{'operation': 'audio_fades', 'target': 'P001-a', 'frames': 2},
                                         {'operation': 'mogrt', 'target': 'P001-a', 'component': 'scoreboard'}]
        report = build(p)[1]
        self.assertEqual(report['pendingHostOperations'], p['postImport'])
        self.assertIn('generated_only', report['qualification'])


if __name__ == '__main__':
    unittest.main()
