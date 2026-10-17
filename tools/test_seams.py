"""Synthetic edit seams: exact coordinates, full coverage and guarded decisions."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/tennis-point-edit-review/scripts'))

from local_model import read, write
from local_media import prepare_media, export_video
from local_editor import Store
from prepare_review import publish
from seam_detect import analyze, settings, scan, partition, make_plan


class SeamTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
    def test_local_motion_evidence_recovers_tiny_foreground_cut(self):
        import cv2
        import numpy as np
        with tempfile.TemporaryDirectory() as work:
            work=Path(work); source=work/'local.mp4'
            writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'mp4v'),30,(640,360))
            for i in range(60):
                image=np.full((360,640,3),(30,100,30),np.uint8)
                x=40+i if i<30 else 300+i
                cv2.rectangle(image,(x,150),(x+9,169),(240,240,240),-1)
                writer.write(image)
            writer.release()
            report=scan(source,work/'scan')
            hit=next(c for c in report['candidates'] if c['frame']==30)
            self.assertIn('motion_residual',hit['signals'])
            self.assertEqual(report['computerVision']['decodedFrames'],60)
            self.assertEqual([c['frame'] for c in report['candidates']],[30])

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
    def test_small_same_view_position_jump_is_not_lost_in_global_background(self):
        with tempfile.TemporaryDirectory() as work:
            work=Path(work);source=work/'small-jump.mp4'
            subprocess.run(['ffmpeg','-v','error',
                '-f','lavfi','-i','color=green:s=320x180:r=30:d=1,drawbox=x=80:y=80:w=12:h=20:c=white:t=fill',
                '-f','lavfi','-i','color=green:s=320x180:r=30:d=1,drawbox=x=160:y=80:w=12:h=20:c=white:t=fill',
                '-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0','-c:v','libx264',str(source)],check=True)
            report=scan(source,work/'scan')
            self.assertEqual([c['frame'] for c in report['candidates']],[30])
            self.assertLess(report['candidates'][0]['difference'],2)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_variable_timing_nonzero_origin_and_timestamp_integrity(self):
        with tempfile.TemporaryDirectory() as work:
            work=Path(work); source=work/'variable.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=25:d=1',
                '-vf',r'setpts=if(lt(N\,10)\,N\,N*2-10)/(25*TB)+5/TB',
                '-fps_mode','vfr','-c:v','libx264',str(source)],check=True)
            report=scan(source,work/'scan')
            self.assertEqual(report['firstPtsUs'],5000000)
            self.assertEqual(report['frameCount'],25)
            self.assertEqual(report['timing']['classification'],'variable_or_discontinuous')
            prepare_media(source,work/'proxy.mp4')
            plan=make_plan(work/'scan/scan.json',work/'proxy.media.json')
            self.assertEqual(plan['clips'][0]['inFrame'],0)
            self.assertEqual(plan['clips'][-1]['outFrame'],read(work/'proxy.media.json')['frames'])
            pts=read(work/'scan/timestamps.json');pts[1]+=10
            (work/'scan/timestamps.json').write_text(json.dumps(pts),encoding='utf-8')
            with self.assertRaises(ValueError): make_plan(work/'scan/scan.json',work/'proxy.media.json')

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_real_decode_repeatability_and_local_plan(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = work/'synthetic.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=blue:s=160x90:r=30000/1001:d=1.001',
                '-f','lavfi','-i','color=red:s=160x90:r=30000/1001:d=1.001',
                '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=2.002',
                '-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]','-map','[v]','-map','2:a',
                '-c:v','libx264','-c:a','aac','-pix_fmt','yuv420p',str(source)], check=True)
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
            write(work/'rough-plan.json',refined)
            publish(work/'rough-plan.json',work/'initial',mode='human-first',provisional=True)
            project=Store(work/'initial/edit').get()
            self.assertEqual(len(project['review']['rows']),3)
            self.assertTrue(all(r['candidatePoint'] and r['initial']=={} for r in project['review']['rows']))
            with self.assertRaisesRegex(ValueError,'Agent render deferred'):
                export_video(project,work/'export')
            self.assertFalse((work/'export').exists())
            with self.assertRaises(ValueError): scan(source, work/'a')
            source.write_bytes(b'changed')
            with self.assertRaises(ValueError): make_plan(work/'a/scan.json', work/'proxy.media.json')


if __name__ == '__main__':
    unittest.main()
