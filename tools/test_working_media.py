"""Working resolution is bounded without lowering original-source export quality."""
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from tools.test_local_editor import sample, SCRIPTS
from working_media import working_size, within_budget
from local_media import prepare_media, export_video, export_settings, run, source_settings
from local_editor import initialize, make_server
from source_inspect import sample as inspect_source
from frame_evidence import evidence as inspect_movement
from precision_evidence import extract
from media_probe import identity


class WorkingSizeTests(unittest.TestCase):
    def test_aspect_orientation_and_small_sources(self):
        for source, expected in [((3840,2160),(1920,1080)), ((2560,1440),(1920,1080)),
                                 ((2160,3840),(1080,1920)), ((2880,2160),(1440,1080)),
                                 ((4096,2160),(1920,1012)), ((640,480),(640,480))]:
            with self.subTest(source=source): self.assertEqual(working_size(*source), expected)
        self.assertEqual(working_size(3840,2160,1280),(1280,720))
        for source, width in [((3840,2160),2560), ((2160,3840),1920), ((640,480),0)]:
            with self.assertRaises(ValueError): working_size(*source,width)

    def test_rotation_and_sar_are_applied_before_cap(self):
        v=dict(codec_type='video',width=2160,height=1440,r_frame_rate='60000/1001',
            avg_frame_rate='60000/1001',sample_aspect_ratio='4:3',side_data_list=[dict(rotation=90)])
        s=source_settings(dict(streams=[v]))
        self.assertEqual((s['width'],s['height']),(1440,2880))
        self.assertEqual(working_size(s['width'],s['height']),(960,1920))
        self.assertEqual(s['fps'],'60000/1001')

    def test_old_export_defaults_and_explicit_output_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            p=sample(directory)
            self.assertEqual(export_settings(p)['width'],320)
            p['exportDefaults']=dict(width=3840,height=2160)
            self.assertEqual(export_settings(p)['width'],3840)
            self.assertEqual(export_settings(p,dict(width=1280,height=720))['width'],1280)


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
class WorkingMediaIntegrationTests(unittest.TestCase):
    def test_capped_analysis_native_roi_and_original_export(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); original=root/'original.mkv'
            run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=2560x1440:rate=30000/1001',
                 '-f','lavfi','-i','sine=frequency=523:sample_rate=48000','-t','0.8',
                 '-c:v','ffv1','-c:a','pcm_s16le',original])
            fingerprint=identity(original)
            meta=prepare_media(original,root/'working.mp4')
            self.assertEqual((meta['width'],meta['height'],meta['fps']),(1920,1080,'30000/1001'))
            self.assertEqual(meta['originalPath'],str(original.resolve()))
            self.assertEqual(meta['sourceIdentity']['sha256'],fingerprint['sha256'])
            self.assertEqual(meta['sourceSettings']['width'],2560)
            # Oversized full frames cannot silently enter image/context caches.
            with self.assertRaisesRegex(ValueError,'1080p'):
                inspect_source(original,.1,.4,root/'oversized',step=.1,job=root)
            with self.assertRaisesRegex(ValueError,'1080p'):
                inspect_movement(original,.1,.4,root/'oversized-motion',job=root)
            with self.assertRaisesRegex(ValueError,'Native ROI'):
                extract(meta,.1,.2,root/'oversized-roi','ending',[0,0,2560,1440],job=root)
            nav=inspect_source(meta['path'],.1,.7,root/'overview',step=.1,width=1000,columns=3,job=root)
            for path in nav['sheets']+[r['raw'] for r in nav['records'] if r['status']=='extracted']:
                with Image.open(path) as im: self.assertTrue(within_budget(*im.size))
            roi=extract(meta,.1,.2,root/'ending','ending',[120,80,160,96],job=root)
            self.assertEqual(roi['sourceSize'],[2560,1440]); self.assertFalse(roi['resampled'])
            self.assertTrue(all(r['pixelSize']==[160,96] for r in roi['records']))
            p=sample(root)
            for key in ('fps','width','height'): p.pop(key)
            p['assets']=[dict(id='src',**meta)]
            p['clips']=[dict(id='cut',assetId='src',pointId='P001',inFrame=3,outFrame=18)]
            p=initialize(p,root/'project')
            self.assertEqual((p['width'],p['height']),(1920,1080))
            self.assertEqual(p['exportDefaults'],dict(width=2560,height=1440))
            # Exercise the documented endpoint CLI with the actual prepared source mapping.
            endpoint_file=root/'endpoints.json'
            command=[sys.executable,'-B',str(SCRIPTS/'endpoint_audit.py'),str(root/'project/project.json')]
            subprocess.run(command+['--template',str(endpoint_file)],check=True,capture_output=True)
            endpoints=json.loads(endpoint_file.read_text(encoding='utf-8'))
            endpoints['records'][0].update(status='verified',
                anchor=dict(kind='next_serve',sourceSeconds='.7',relation='unknown'),
                lastLiveSeconds='.45',endWindowSeconds=['.5','.53'],retainThroughSeconds='.57',
                forwardWindowSeconds=['.4','.67'],continuationFound=False,
                reason='Synthetic timing fixture only',evidence=['ending/evidence.json'])
            endpoint_file.write_text(json.dumps(endpoints),encoding='utf-8')
            checked=subprocess.run(command+['--evidence',str(endpoint_file)],check=True,capture_output=True,text=True)
            self.assertTrue(json.loads(checked.stdout)['complete'])
            # The unchanged export dialog obtains its dimensions from this API.
            server=make_server(root/'project',0)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                client=http.client.HTTPConnection('127.0.0.1',server.server_port)
                client.request('GET','/api/export-settings',headers={'X-Session-Token':server.launch_url.split('token=')[1]})
                response=client.getresponse(); settings=json.loads(response.read()); client.close()
                self.assertEqual(response.status,200)
                self.assertEqual((settings['width'],settings['height']),(2560,1440))
            finally:
                server.shutdown(); server.server_close(); thread.join()
            # Removing the proxy proves that final rendering still reads the original.
            Path(meta['path']).unlink()
            result=export_video(p,root/'export',user_requested=True)
            video=next(s for s in result['probe']['streams'] if s['codec_type']=='video')
            self.assertEqual((video['width'],video['height']),(2560,1440))
            self.assertEqual(result['frames'],15)
            self.assertEqual((result['render']['videoEncodes'],result['render']['audioEncodes']),(1,1))
            self.assertEqual(result['render']['intermediateMediaBytes'],0)
            self.assertEqual(identity(original)['sha256'],fingerprint['sha256'])


if __name__ == '__main__': unittest.main()
