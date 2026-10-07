"""Local editor invariants, review parity, HTTP isolation and actual media export."""
import copy
import http.client
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from fractions import Fraction
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/tennis-point-edit-review/scripts'
sys.path.insert(0, str(SCRIPTS))
from local_model import SCHEMA, Store, Conflict, write, validate, layout, review_payload, overlay_range, context
from local_editor import make_server, initialize
from local_media import export_video, export_settings, prepare_media, probe, run, source_settings


class OutputLanguageTests(unittest.TestCase):
    def test_saved_language_is_available_on_resume(self):
        with tempfile.TemporaryDirectory() as d:
            project=sample(d)
            project['outputLanguage']='en-US'
            validate(project)
            self.assertEqual(context(project)['outputLanguage'],'en')
            project['outputLanguage']='fr'
            with self.assertRaises(ValueError): validate(project)


def sample(directory):
    media = Path(directory) / 'source.mp4'
    media.write_bytes(b'0123456789')
    return dict(schema=SCHEMA, revision=0, title='Synthetic review', fps='30', width=320, height=180,
        players=[{'id': 'A', 'name': 'Player A'}, {'id': 'B', 'name': 'Player B'}],
        assets=[dict(id='src', path=str(media), frames=120, hasAudio=False, timing='cfr-proxy')],
        clips=[dict(id='first', assetId='src', pointId='P001', inFrame=10, outFrame=40),
               dict(id='second', assetId='src', pointId='P002', inFrame=60, outFrame=90)],
        overlays=[], review=dict(source='synthetic', ledgerRevision='v1', rows=[
            dict(reviewId='R001', pointId='P001', serverId='A'),
            dict(reviewId='R002', pointId='P002', serverId='B', countingIssueRequired=True)]),
        answers={}, needsRebuild=[], undo=[], redo=[], events=[])


class ModelTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = sample(self.temp.name)
        write(Path(self.temp.name) / 'project.json', self.p)
        self.store = Store(self.temp.name)

    def test_frame_ranges_and_validation(self):
        self.assertEqual([c['startFrame'] for c in layout(self.p)], [0, 30])
        self.assertEqual(overlay_range(dict(anchor='source', startFrame=5, endFrame=20), self.p['clips'][0]), (0, 10))
        self.p['clips'][0]['outFrame'] = 121
        with self.assertRaises(ValueError): validate(self.p)
        self.p['clips'][0]['outFrame'] = 10
        with self.assertRaises(ValueError): validate(self.p)

    def test_review_subset_does_not_require_clear_points_to_be_reviewed(self):
        self.p['review']['rows'] = self.p['review']['rows'][1:]
        project = validate(self.p)
        write(Path(self.temp.name) / 'subset/project.json', project)
        store = Store(Path(self.temp.name) / 'subset')
        changed = store.apply(0, dict(type='trim', id='first', inFrame=11, outFrame=40))
        self.assertEqual([c['pointId'] for c in layout(changed)], ['P001', 'P002'])
        self.assertEqual(review_payload(changed)['totalRows'], 1)
        self.assertEqual(review_payload(changed)['rows'][0]['pointId'], 'P002')
        self.assertEqual(project['review']['rows'], self.p['review']['rows'])
        # An unlisted point cannot acquire a fabricated human-review answer.
        changed['answers']['P001'] = dict(scoringPlayerId='A', reviewConfirmed=True)
        with self.assertRaisesRegex(ValueError, 'Unknown answer point'):
            validate(changed)

    def test_main_cut_without_review_keeps_point_locators(self):
        self.p['review']['rows'] = []
        project = validate(self.p)
        write(Path(self.temp.name) / 'main-only/project.json', project)
        restored = Store(Path(self.temp.name) / 'main-only').get()
        self.assertEqual(restored['clips'], project['clips'])
        self.assertEqual(review_payload(restored)['rows'], [])
        self.assertEqual([c['pointId'] for c in layout(restored)], ['P001', 'P002'])
        for invalid in ('', '   ', 1, []):
            restored['clips'][0]['pointId'] = invalid
            with self.assertRaisesRegex(ValueError, 'Invalid clip point ID'):
                validate(restored)

    def test_conflict_and_undo_redo_preserve_answers(self):
        first = self.store.apply(0, dict(type='review', pointId='P001', answer=dict(scoringPlayerId='B', deadBallType='net', reviewConfirmed=True)))
        with self.assertRaises(Conflict): self.store.apply(0, dict(type='reorder', ids=['second', 'first']))
        second = self.store.apply(1, dict(type='trim', id='first', inFrame=11, outFrame=40))
        undone = self.store.apply(2, dict(type='undo'))
        self.assertEqual(undone['answers'], first['answers'])
        self.assertEqual(undone['clips'][0]['inFrame'], 10)
        self.assertEqual(undone['needsRebuild'], ['score-and-statistics'])
        redone = self.store.apply(3, dict(type='redo'))
        self.assertEqual(redone['clips'], second['clips'])
        self.assertTrue((Path(self.temp.name) / 'history/000003.json').is_file())

    def test_unknown_replay_extra_and_counting_issue(self):
        self.p['answers']['P001'] = dict(scoringPlayerId='A', deadBallType='ace', winnerUndetermined=True, reviewConfirmed=True)
        row = review_payload(self.p)['rows'][0]
        self.assertEqual(row['status'], 'unresolved')
        self.assertIsNone(row['scoringPlayerId'])
        self.assertIsNone(row['deadBallType'])
        self.assertTrue(row['inferenceRequired'])
        self.p['answers']['P001']['extra'] = True
        self.assertFalse(review_payload(self.p)['rows'][0]['inferenceRequired'])
        self.p['answers']['P001'] = dict(deadBallType='replay', reviewConfirmed=False)
        row = review_payload(self.p)['rows'][0]
        self.assertEqual(row['status'], 'partial')
        self.assertFalse(row['countsTowardScore'])
        self.p['answers']['P002'] = dict(scoringPlayerId='A', deadBallType='net', reviewConfirmed=True)
        self.assertEqual(review_payload(self.p)['rows'][1]['status'], 'partial')

    def test_invalid_edits_leave_revision_intact(self):
        for operation in [dict(type='reorder', ids=['first','first']), dict(type='trim',id='first',inFrame=30,outFrame=30),
                          dict(type='review',pointId='P001',answer=dict(scoringPlayerId='B', deadBallType='ace'))]:
            with self.assertRaises(ValueError): self.store.apply(0, operation)
            self.assertEqual(self.store.get()['revision'], 0)

    def test_export_filename_and_dimensions_validation(self):
        self.p['needsRebuild'] = ['score-and-statistics']
        self.assertEqual(export_settings(self.p, {'filename':'Match 你好'})['filename'], 'Match 你好.mp4')
        for opts in [{'filename':'../bad'}, {'filename':'CON.mp4'}, {'width':321}, {'fps':'0'}, {'fps':'241'}]:
            with self.assertRaises(ValueError): export_settings(self.p, opts)

    def test_cli_reconciliation_preserves_answers_and_rejects_mapping_changes(self):
        current = self.store.apply(0, dict(type='review', pointId='P001', answer=dict(scoringPlayerId='B', deadBallType='net', reviewConfirmed=True)))
        plan = Path(self.temp.name) / 'update.json'
        proposed = copy.deepcopy(current); proposed['answers'] = {}; proposed['title'] = 'Reconciled'
        write(plan, proposed)
        command = [sys.executable, str(SCRIPTS/'local_editor.py'), 'update', self.temp.name, str(plan), '--expected-revision']
        result = subprocess.run([*command,'1'],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        actual = self.store.get()
        self.assertEqual(actual['answers'],current['answers'])
        self.assertEqual(actual['needsRebuild'],[])
        self.assertEqual(actual['revision'],2)
        proposed['review']['rows'][0]['reviewId'] = 'R999'
        write(plan, proposed)
        result = subprocess.run([*command,'2'],capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.store.get()['revision'],2)

    def test_http_tokens_origins_ranges_and_revision(self):
        server = make_server(self.temp.name)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        token = server.launch_url.split('token=')[1]
        def request(method, path, body=None, headers=None):
            c = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            c.request(method, path, json.dumps(body) if body is not None else None, headers or {})
            r = c.getresponse(); result = (r.status, r.read(), dict(r.getheaders())); c.close(); return result
        self.assertEqual(request('GET','/api/project')[0],403)
        for path in ['/i18n.js', '/view-state.js']:
            status, body, headers = request('GET', path)
            self.assertEqual(status, 200)
            self.assertIn(b'export ', body)
        self.assertEqual(request('GET','/api/project',headers={'X-Session-Token':token,'Origin':'https://example.org'})[0],403)
        self.assertEqual(request('GET','/../../project.json',headers={'X-Session-Token':token})[0],404)
        status, body, headers = request('GET','/media/src',headers={'X-Session-Token':token,'Range':'bytes=2-4'})
        self.assertEqual((status,body,headers['Content-Range']), (206,b'234','bytes 2-4/10'))
        self.assertEqual(request('GET','/media/src',headers={'X-Session-Token':token,'Range':'bytes=99-'})[0],416)
        op = dict(revision=0, operation=dict(type='reorder',ids=['second','first']))
        self.assertEqual(request('POST','/api/operation',op,{'X-Session-Token':token})[0],200)
        self.assertEqual(request('POST','/api/operation',op,{'X-Session-Token':token})[0],409)
        with patch('local_editor.export_video', return_value={'state':'complete'}) as render:
            status, body, _ = request('POST','/api/render',{'revision':1,'options':{'filename':'用户选择.mp4','fps':'25','width':640,'height':360}},{'X-Session-Token':token})
            self.assertEqual(status,202,body)
            render.assert_called_once()
            args = render.call_args.args
            self.assertEqual(args[0]['needsRebuild'], ['presentation-order'])
            self.assertEqual(args[3]['fps'], '25')
            self.assertEqual(args[4].name, '用户选择.mp4')
        with patch('local_editor.pick_directory', return_value=self.temp.name) as picker:
            status, body, _ = request('POST','/api/pick-directory',{'directory':self.temp.name},{'X-Session-Token':token})
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)['directory'],self.temp.name)
            picker.assert_called_once()
        with patch('local_editor.pick_directory', return_value=''):
            self.assertEqual(json.loads(request('POST','/api/pick-directory',{}, {'X-Session-Token':token})[1])['directory'],'')



@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class MediaTest(unittest.TestCase):
    def test_source_defaults_and_fps_override_preserve_evidence_and_duration(self):
        for source_rate, output_rate in [('25','60'), ('30000/1001','24'), ('60','30000/1001')]:
            with self.subTest(rate=source_rate), tempfile.TemporaryDirectory() as tmp:
                p = sample(tmp)
                raw = Path(tmp)/'raw.mp4'
                run(['ffmpeg','-v','error','-f','lavfi','-i',f'testsrc2=size=320x240:rate={source_rate}',
                     '-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','3','-c:v','libx264','-c:a','aac',raw])
                meta = prepare_media(raw,Path(tmp)/'prepared.mp4')
                self.assertEqual((meta['width'],meta['height'],meta['fps']),(320,240,source_rate))
                self.assertEqual(meta['audio'],dict(sampleRate=44100,channels=1))
                for key in ('fps','width','height'): p.pop(key)
                p['assets'][0] = {'id':'src', **meta}
                p['clips'] = [dict(id='first',assetId='src',pointId='P001',inSeconds='.4',outSeconds='1.4'),
                              dict(id='hold',assetId='src',kind='hold',inSeconds='1.4',durationSeconds='.3')]
                p['review']['rows'] = []
                project = initialize(p, Path(tmp)/'project')
                self.assertEqual(review_payload(project)['rows'], [])
                self.assertEqual((project['width'],project['height'],project['fps']),(320,240,source_rate))
                self.assertEqual(project['clips'][0]['inFrame'],round(Fraction(2,5)*Fraction(source_rate)))
                project['needsRebuild'] = ['presentation-order','score-and-statistics']
                before = copy.deepcopy(project)
                result = export_video(project,Path(tmp)/'render',options=dict(width=640,height=480,fps=output_rate,filename='custom 中文.mp4'))
                self.assertEqual(project,before)
                self.assertEqual(result['warnings'],project['needsRebuild'])
                video = next(x for x in result['probe']['streams'] if x['codec_type']=='video')
                audio = next(x for x in result['probe']['streams'] if x['codec_type']=='audio')
                self.assertEqual((video['width'],video['height'],Fraction(video['avg_frame_rate'])),(640,480,Fraction(output_rate)))
                self.assertEqual((audio['sample_rate'],audio['channels']),('44100',1))
                seconds = sum(c['endFrame']-c['startFrame'] for c in layout(project))/float(Fraction(source_rate))
                self.assertLessEqual(abs(float(video['duration'])-seconds), .501/float(Fraction(output_rate))+1e-6)
                self.assertTrue(Path(result['path']).name.startswith('custom 中文'))
                with self.assertRaisesRegex(ValueError,'already exists'):
                    export_video(project,Path(tmp)/'another',target=result['path'])

    def test_overlay_half_open_frames_and_stats_fade(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = sample(tmp)
            source = Path(p['assets'][0]['path'])
            run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:size=320x180:rate=30','-t','4','-c:v','libx264',source])
            graphic = Path(tmp) / 'red.png'
            run(['ffmpeg','-v','error','-f','lavfi','-i','color=red:size=320x180,format=rgba','-frames:v','1',graphic])
            p['clips'] = [dict(id='clip',assetId='src',pointId='P001',inFrame=0,outFrame=30)]
            for component,start,end,visible,hidden in [('serveLabel',5,15,[5,14],[4,15]),('statsPanel',0,30,[9,20],[0,29])]:
                p['overlays'] = [dict(id='overlay',clipId='clip',component=component,startFrame=start,endFrame=end,image=str(graphic))]
                for output_rate in (30,60):
                    result = export_video(p,Path(tmp)/(component+str(output_rate)),options={'fps':str(output_rate)})
                    pixels = subprocess.check_output(['ffmpeg','-v','error','-i',result['path'],'-vf','scale=4:4','-f','rawvideo','-pix_fmt','rgb24','-'])
                    self.assertEqual(len(pixels),output_rate*4*4*3)
                    reds = [pixels[n*48] for n in range(output_rate)]
                    for n in visible: self.assertGreater(reds[n*output_rate//30],200,(component,n,reds))
                    for n in hidden: self.assertLess(reds[n*output_rate//30],20,(component,n,reds))

    def test_real_cut_export_frame_count_audio_and_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = sample(tmp)
            raw = Path(tmp) / 'generated.mp4'
            run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=30',
                 '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','4','-c:v','libx264','-c:a','aac',raw])
            proxy = Path(tmp) / 'proxy.mp4'
            meta = prepare_media(raw,proxy,width=320)
            p['assets'][0].update(meta)
            p['clips'].append(dict(id='hold',kind='hold',assetId='src',inFrame=89,durationFrames=30))
            result = export_video(p, Path(tmp) / 'render')
            self.assertEqual(result['frames'],90)
            info = probe(result['path'])
            video = next(s for s in info['streams'] if s['codec_type']=='video')
            self.assertEqual(video['avg_frame_rate'],'30/1')
            self.assertAlmostEqual(float(video['duration']),3,places=2)
            self.assertTrue(any(s['codec_type']=='audio' for s in info['streams']))
            # Output source windows really differ; the hold must retain the last source image.
            def pixels(file,frame):
                return subprocess.check_output(['ffmpeg','-v','error','-i',str(file),'-vf',f'select=eq(n\\,{frame}),scale=8:8',
                    '-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
            a,b,c = [pixels(result['path'],n) for n in (0,30,89)]
            self.assertNotEqual(a,b)
            source_hold = pixels(proxy,89)
            self.assertLess(sum(abs(x-y) for x,y in zip(c,source_hold))/len(c),12)

if __name__ == '__main__': unittest.main()
