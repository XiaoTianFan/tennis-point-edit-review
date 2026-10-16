"""Synthetic edit seams: exact coordinates, full coverage and guarded decisions."""
import copy
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from local_model import read
from local_media import prepare_media
from seam_detect import analyze, settings, scan, partition, make_plan


class SeamTests(unittest.TestCase):
    def test_same_court_small_jump_and_motion_baseline(self):
        rows = [dict(frame=i, ptsUs=i*40000, difference=1.0, sceneScore=0.2) for i in range(60)]
        rows[30].update(difference=4.0, sceneScore=0.3)
        _, candidates, _ = analyze(rows, settings(), dict(avg_frame_rate='25'))
        self.assertEqual([c['frame'] for c in candidates], [30])
        self.assertEqual(candidates[0]['signals'], ['adaptive_difference'])
        # Sustained movement is a baseline, not one seam at every moving frame.
        moving = [dict(frame=i, ptsUs=i*40000, difference=5.0, sceneScore=0.1) for i in range(60)]
        self.assertEqual([c['frame'] for c in analyze(moving, settings(), {})[1]], [])

    def test_flash_adjacent_hits_are_retained_and_flagged(self):
        rows = [dict(frame=i, ptsUs=i*40000, difference=80 if i in (3,4) else 0,
                     sceneScore=80 if i == 3 else 0) for i in range(8)]
        _, candidates, _ = analyze(rows, settings(), {})
        self.assertEqual([c['frame'] for c in candidates], [3,4])
        self.assertTrue(all(c['adjacentHit'] for c in candidates))

    def test_decision_fences_and_half_open_coverage(self):
        report = dict(schema='tennis-seams/v1', scanId='synthetic-scan', source=dict(sha256='synthetic'),
                      frameCount=10, candidates=[dict(frame=3), dict(frame=4)])
        self.assertEqual([(c['inFrame'], c['outFrame']) for c in partition(report)], [(0,3),(3,4),(4,10)])
        decision = dict(schema='tennis-seam-decisions/v1', scanId='synthetic-scan', sourceSha256='synthetic',
                        boundaryFrames=[2,7], status='reviewed')
        clips = partition(report, decision)
        self.assertEqual(sum(c['outFrame']-c['inFrame'] for c in clips), 10)
        for frames in ([7,2], [2,2], [0], [10], [2.0], [True]):
            with self.assertRaises(ValueError): partition(report, {**decision, 'boundaryFrames': frames})
        with self.assertRaises(ValueError): partition(report, {**decision, 'scanId': 'stale'})
        self.assertEqual(len(partition({**report, 'candidates': []})), 1)

    def test_reject_incomplete_or_nonmonotone_metrics(self):
        with self.assertRaises(ValueError): analyze([], settings(), {})
        rows = [dict(frame=i, ptsUs=0, difference=0, sceneScore=0) for i in range(2)]
        with self.assertRaises(ValueError): analyze(rows, settings(), {})
        with self.assertRaises(ValueError): settings(dict(differenceFloor=float('nan')))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_real_decode_repeatability_and_local_plan(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = work/'synthetic.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=blue:s=160x90:r=30000/1001:d=1.001',
                '-f','lavfi','-i','color=red:s=160x90:r=30000/1001:d=1.001',
                '-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0','-c:v','libx264','-pix_fmt','yuv420p',str(source)], check=True)
            a = scan(source, work/'a'); b = scan(source, work/'b')
            self.assertEqual(a, b)
            self.assertEqual(a['frameCount'], 60)
            self.assertEqual([c['frame'] for c in a['candidates']], [30])
            prepare_media(source, work/'proxy.mp4')
            plan = make_plan(work/'a/scan.json', work/'proxy.media.json')
            self.assertEqual([(c['inFrame'],c['outFrame']) for c in plan['clips']], [(0,30),(30,60)])
            self.assertTrue(all('pointId' not in c for c in plan['clips']))
            self.assertEqual(plan['review']['rows'], [])
            # A manually added boundary remains frame exact at fractional rates.
            d = read(work/'a/decisions.json'); d['boundaryFrames'] = [15,30]
            refined = make_plan(work/'a/scan.json', work/'proxy.media.json', d)
            self.assertEqual(refined['clips'][1]['inFrame'], 15)
            self.assertLess(abs(refined['clips'][1]['sourceMapping']['proxyBoundaryErrorUs']), 1)
            with self.assertRaises(ValueError): scan(source, work/'a')
            source.write_bytes(b'changed')
            with self.assertRaises(ValueError): make_plan(work/'a/scan.json', work/'proxy.media.json')


if __name__ == '__main__':
    unittest.main()
