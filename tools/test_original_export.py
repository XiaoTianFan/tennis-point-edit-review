"""Behavioral regression: original timing, single audio clock and bounded streams."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools.test_local_editor import sample, bind_fixture, SCRIPTS
from local_media import prepare_media, export_video, run, probe
from local_render import pcm_chunk, video_command, nearest
from source_binding import bind_legacy


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
class OriginalExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def source(self, name='original.mkv', offset=0, audio=True, bt709=False):
        path = self.root/name
        args = ['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x96:rate=60000/1001']
        if audio:
            args += ['-f','lavfi','-i','anoisesrc=seed=73:sample_rate=48000:amplitude=0.2']
        if bt709:
            args += ['-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709','-color_range','tv']
        run(args+['-t','5','-c:v','ffv1','-c:a','pcm_s16le','-output_ts_offset',str(offset),path])
        return path

    def project(self, source, start=0):
        p=sample(self.root); meta=prepare_media(source,self.root/'proxy.mp4',start=start,length=3)
        p.update(fps=meta['fps'], width=meta['width'], height=meta['height'], audio=meta['audio'])
        p['assets']=[dict(id='src',**meta)]
        p['review']['rows']=[]
        return p

    def test_many_cuts_do_not_accumulate_aac_padding_and_hold_is_silent(self):
        import numpy as np
        from scipy.signal import correlate, correlation_lags
        p=self.project(self.source())
        lengths=[19,23,41,17,29,37,31,43,25,47,21,39,35,27,33,45]
        p['clips']=[dict(id=f'cut{i}',assetId='src',pointId=f'P{i:03}',inFrame=(i*7)%80,outFrame=(i*7)%80+n) for i,n in enumerate(lengths)]
        p['clips'].append(dict(id='hold',kind='hold',assetId='src',inFrame=10,durationFrames=31))
        rate=Fraction(p['fps']); asset=p['assets'][0]
        full_pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',asset['originalPath'],'-f','f32le','-ac','1','-']),dtype='<f4')
        reference=[]; global_frame=0
        for clip in p['clips']:
            n=clip.get('durationFrames',clip.get('outFrame',0)-clip['inFrame'])
            length=nearest(Fraction(global_frame+n)*48000/rate)-nearest(Fraction(global_frame)*48000/rate)
            first=nearest(Fraction(clip['inFrame'])*48000/rate)
            reference.append((full_pcm[first:first+length] if clip.get('kind')!='hold' else np.zeros(length))[:,None]);global_frame+=n
        # Delete proxy: export has no dependency on its bytes or existence.
        Path(asset['path']).unlink()
        with patch('local_render.CHUNK_SECONDS',Fraction(1,4)):
            result=export_video(p,self.root/'export',user_requested=True)
        actual=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',result['path'],'-f','f32le','-ac','1','-']),dtype='<f4')
        start=0; lags=[]
        for block in reference[:-1]:
            expected=block[:,0]; mid=expected[2200:-2200]
            candidate=actual[start+2200-800:start+len(expected)-2200+800]
            corr=correlate(candidate,mid,method='fft'); lag=correlation_lags(len(candidate),len(mid))[corr.argmax()]-800
            lags.append(int(lag)); start+=len(expected)
        self.assertLessEqual(max(abs(x) for x in lags),2,lags)
        self.assertLess(float(np.sqrt(np.mean(actual[start+3000:start+10000]**2))),.0001)
        self.assertEqual(result['render']['audioSamples'],nearest(Fraction(result['frames'])*48000/rate))
        self.assertLess(result['render']['maxPcmBytes'],48000*4)
        self.assertEqual(result['render']['intermediateMediaBytes'],0)
        self.assertEqual(sorted(x.name for x in (self.root/'export').iterdir()),['edited.mp4','export.json','project-snapshot.json'])
        audio=next(x for x in result['probe']['streams'] if x['codec_type']=='audio')
        self.assertLessEqual(abs(Fraction(audio['duration_ts'])*Fraction(audio['time_base'])-Fraction(result['render']['audioSamples'],48000)),Fraction(1,48000))

    def test_nonzero_source_start_and_container_pts_match_proxy_grid(self):
        p=self.project(self.source(offset=5),start=.47)
        asset=p['assets'][0]
        self.assertEqual(next(x for x in probe(asset['path'])['streams'] if x['codec_type']=='video')['start_pts'],0)
        p['clips']=[dict(id='cut',assetId='src',pointId='P001',inFrame=17,outFrame=47)]
        settings=dict(width=p['width'],height=p['height'])
        raw=subprocess.check_output(video_command(p,settings,asset,p['clips'][0],0,30))
        expected=subprocess.check_output(['ffmpeg','-v','error','-i',asset['path'],'-vf','trim=start_frame=17:end_frame=47,setpts=PTS-STARTPTS,scale=160:96:out_range=tv:out_color_matrix=bt709','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','yuv420p','-'])
        import numpy as np
        difference=np.frombuffer(raw,dtype=np.uint8).astype(float)-np.frombuffer(expected,dtype=np.uint8)
        self.assertLess(np.mean(difference**2),15)  # Proxy loss only, not a one-frame shift.
        result=export_video(p,self.root/'export',user_requested=True)
        full_pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',asset['originalPath'],'-f','f32le','-ac','1','-']),dtype='<f4')
        first=nearest((Fraction(47,100)+Fraction(17)/Fraction(p['fps']))*48000)
        original=full_pcm[first:first+nearest(Fraction(30)*48000/Fraction(p['fps']))]
        actual=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',result['path'],'-f','f32le','-ac','1','-']),dtype='<f4')
        from scipy.signal import correlate, correlation_lags
        a,b=actual[2000:len(original)-2000],original[2000:-2000]
        self.assertGreater(np.corrcoef(a,b)[0,1],.7)  # AAC attenuates wideband noise.
        self.assertEqual(int(correlation_lags(len(a),len(b))[correlate(a,b,method='fft').argmax()]),0)

    def test_source_identity_missing_replaced_and_legacy_binding(self):
        p=self.project(self.source(audio=False))
        p['clips']=[dict(id='cut',assetId='src',pointId='P001',inFrame=1,outFrame=15)]
        asset=p['assets'][0]
        old=copy.deepcopy(asset); old.pop('sourceIdentity'); old.pop('sourceMapping')
        old['sourceStartSeconds']=0
        accepted=bind_legacy(old)
        self.assertIn('historical identity not established',accepted['binding'])
        old['sourceStartSeconds']=.1
        with self.assertRaisesRegex(ValueError,'Ambiguous'): bind_legacy(old)
        p['assets'][0]=old
        with self.assertRaisesRegex(ValueError,'Unbound'):export_video(p,self.root/'bad',user_requested=True)
        self.assertFalse((self.root/'bad').exists())
        p['assets'][0]=asset
        wrong=copy.deepcopy(asset);wrong['sourceMapping']['originSeconds']='1'
        p['assets'][0]=wrong
        with self.assertRaisesRegex(ValueError,'timing mapping mismatch'):export_video(p,self.root/'bad',user_requested=True)
        p['assets'][0]=asset
        with Path(asset['originalPath']).open('r+b') as f: f.seek(-1,2); f.write(b'!')
        with self.assertRaisesRegex(ValueError,'identity mismatch'):export_video(p,self.root/'bad',user_requested=True)
        Path(asset['originalPath']).unlink()
        with self.assertRaisesRegex(ValueError,'Original unavailable'):export_video(p,self.root/'bad',user_requested=True)

    def test_chunk_boundaries_do_not_change_video_or_overlay_fades(self):
        p=self.project(self.source(audio=False))
        p['clips']=[dict(id='cut',assetId='src',pointId='P001',inFrame=13,outFrame=103)]
        graphic=self.root/'red.png'
        run(['ffmpeg','-v','error','-f','lavfi','-i','color=red:size=160x96,format=rgba','-frames:v','1',graphic])
        p['overlays']=[dict(id='stats',clipId='cut',component='statsPanel',startFrame=5,endFrame=87,image=str(graphic))]
        asset=p['assets'][0]; clip=p['clips'][0]; settings=dict(width=160,height=96)
        whole=subprocess.check_output(video_command(p,settings,asset,clip,0,90))
        pieces=b''.join(subprocess.check_output(video_command(p,settings,asset,clip,o,min(19,90-o))) for o in range(0,90,19))
        self.assertEqual(whole,pieces)

    def test_small_review_canvas_never_downsamples_original_before_large_export(self):
        # Isolate spatial sampling from unspecified-color conversion rounding,
        # which differs between FFmpeg/libswscale versions and thread settings.
        p=self.project(self.source(audio=False,bt709=True))
        p.update(width=80,height=48)
        clip=dict(id='cut',assetId='src',pointId='P001',inFrame=13,outFrame=43)
        p['clips']=[clip];asset=p['assets'][0]
        actual=subprocess.check_output(video_command(p,dict(width=160,height=96),asset,clip,0,30))
        expected=subprocess.check_output(['ffmpeg','-v','error','-filter_threads','1','-i',asset['originalPath'],'-vf',
            f"settb=AVTB,fps={p['fps']}:start_time=0:round=near,trim=start_frame=13:end_frame=43,setpts=PTS-STARTPTS,scale=160:96:flags=lanczos:out_range=tv:out_color_matrix=bt709",
            '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','yuv420p','-'])
        self.assertEqual(actual,expected)
        degraded=subprocess.check_output(['ffmpeg','-v','error','-filter_threads','1','-i',asset['originalPath'],'-vf',
            f"settb=AVTB,fps={p['fps']}:start_time=0:round=near,trim=start_frame=13:end_frame=43,setpts=PTS-STARTPTS,scale=80:48,scale=160:96",
            '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','yuv420p','-'])
        import numpy as np
        delta=np.frombuffer(actual,dtype=np.uint8).astype(float)-np.frombuffer(degraded,dtype=np.uint8)
        self.assertGreater(float(np.mean(delta**2)),10)

    def test_interrupted_export_closes_decoder_and_can_retry(self):
        p=self.project(self.source(audio=False))
        p['clips']=[dict(id='cut',assetId='src',pointId='P001',inFrame=5,outFrame=120)]
        def interrupt(value):
            if value['progressPercent']>0:raise RuntimeError('Synthetic interruption')
        with self.assertRaisesRegex(RuntimeError,'Synthetic interruption'):
            export_video(p,self.root/'interrupted',interrupt,user_requested=True)
        self.assertFalse((self.root/'interrupted'/'export.json').exists())
        self.assertFalse((self.root/'interrupted'/'edited.mp4').exists())
        result=export_video(p,self.root/'retry',user_requested=True)
        self.assertEqual(result['frames'],115)


if __name__=='__main__': unittest.main()
