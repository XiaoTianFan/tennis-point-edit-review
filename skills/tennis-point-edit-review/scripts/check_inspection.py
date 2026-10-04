"""Synthetic timing, evidence and numbering checks; no real match fixtures."""
from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from evidence_audit import display_order
from media_probe import assess_timestamps, probe


class InspectionChecks(unittest.TestCase):
    def test_display_order_survives_removed_and_merged_points(self):
        ids = ['P002', 'P007', 'P010']
        result = display_order(ids, 'synthetic-2')
        self.assertEqual(result['count'], 3)
        self.assertEqual(result['points'][-1], {'pointId': 'P010', 'displayNumber': 3})
        self.assertEqual(ids, ['P002', 'P007', 'P010'])
        with self.assertRaises(ValueError):
            display_order(['P002', 'P002'], 'synthetic-2')
        self.assertEqual(display_order([], 'empty')['count'], 0)

    def test_quantized_cfr_and_nonzero_origin(self):
        pts = [9000+round(i*Fraction(1001,60)) for i in range(1000)]
        result = assess_timestamps(iter(pts), '1/1000', ['60000/1001'])
        self.assertEqual(result['classification'], 'cfr')
        self.assertEqual(len(result['intervalTicks']), 2)

    def test_equal_summary_rate_cannot_hide_irregular_pts(self):
        result = assess_timestamps([0,30,90,120,180], '1/900', ['20', '20'])
        self.assertEqual(result['classification'], 'variable_or_discontinuous')

    def test_inadequate_evidence_is_unknown(self):
        for pts in ([0,30], [0,None,60], [0,30,30]):
            self.assertEqual(assess_timestamps(pts, '1/900', ['30'])['classification'], 'unknown')
        self.assertEqual(assess_timestamps([0,1,2], '1/30', ['30'])['classification'], 'unknown')

    def test_color_and_motion_diagnostics_are_separate(self):
        try:
            import numpy as np
            from frame_evidence import candidate_mask
        except ImportError:
            self.skipTest('Optional OpenCV/NumPy unavailable')
        frame = np.zeros((30,30,3), np.uint8)
        frame[10:13,10:13] = (92,122,113)  # synthetic olive patch, BGR
        diff = np.zeros((30,30), np.uint8)
        _, counts = candidate_mask(frame,diff,(0,0,30,30),(18,42,80),(62,255,255),12)
        self.assertEqual(counts['afterColor'], 9)
        self.assertEqual(counts['afterMotion'], 0)
        diff[10:13,10:13] = 30
        _, counts = candidate_mask(frame,diff,(0,0,5,5),(18,42,80),(62,255,255),12)
        self.assertEqual(counts['afterMotion'], 9)
        self.assertEqual(counts['afterRoi'], 0)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg/ffprobe unavailable')
class MediaChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.cfr = cls.root/'synthetic.mp4'
        cls.vfr = cls.root/'variable.mp4'
        common = ['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=30:duration=1',
                  '-an','-c:v','libx264','-pix_fmt','yuv420p']
        subprocess.run([*common, str(cls.cfr)],check=True,capture_output=True)
        subprocess.run([*common,'-vf','setpts=(N+floor(N/2))/(30*TB)',
                        '-fps_mode','vfr',str(cls.vfr)],check=True,capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_actual_pts_and_exchange_preflight(self):
        from premiere_exchange import build
        cfr, vfr = probe(self.cfr), probe(self.vfr)
        self.assertEqual(cfr['timing']['classification'], 'cfr')
        self.assertEqual(cfr['timing']['frameCount'], 30)
        self.assertEqual(vfr['timing']['classification'], 'variable_or_discontinuous')
        plan = {'schema':'tennis-edit-plan/v1','revision':'synthetic',
                'sequence':{'name':'Synthetic','fps':'30','width':320,'height':180,'durationFrames':30},
                'assets':[{'id':'source','path':str(self.cfr),'kind':'video','width':320,'height':180,
                           'fps':'30','durationFrames':30,'timing':'cfr','timingEvidence':'synthetic','audioChannels':0}],
                'clips':[{'id':'clip','assetId':'source','track':1,'startFrame':0,'durationFrames':30}]}
        self.assertEqual(build(plan,probe_media=True)[1]['mediaTimingChecks']['source']['source']['sha256'],
                         cfr['source']['sha256'])
        plan['assets'][0]['path'] = str(self.vfr)
        with self.assertRaisesRegex(ValueError, 'Unverified CFR'):
            build(plan,probe_media=True)
        # Offline interchange remains available, without silently claiming a probe.
        self.assertNotIn('mediaTimingChecks',build(plan)[1])

    def test_samples_keep_full_frames_and_detector_can_be_disabled(self):
        try:
            import cv2
            from frame_evidence import evidence
        except ImportError:
            self.skipTest('Optional OpenCV/NumPy unavailable')
        from source_inspect import sample
        out = self.root/'samples'
        result = sample(self.cfr,0,1,out,step=.25,roi=[10,10,100,100],width=200,page_size=2)
        self.assertEqual(len(result['sheets']), 2)
        self.assertEqual(result['visualReview'],'not_performed')
        for record in result['records']:
            self.assertEqual(record['status'],'extracted')
            self.assertEqual(cv2.imread(str(out/record['raw'])).shape[:2],(180,320))
            self.assertLess(abs(record['seekErrorSeconds']),1/30)
        manifest = evidence(self.cfr,.1,.3,self.root/'native',candidates_enabled=False)
        self.assertGreater(len(manifest['records']), 1)
        self.assertFalse(manifest['detector']['enabled'])
        self.assertTrue(all(r['candidates'] is None for r in manifest['records']))
        self.assertTrue(all(.1 <= r['timeSeconds'] < .3 for r in manifest['records']))
        with self.assertRaises(ValueError):
            evidence(self.cfr,.1,.3,self.root/'native')


if __name__ == '__main__':
    unittest.main()
