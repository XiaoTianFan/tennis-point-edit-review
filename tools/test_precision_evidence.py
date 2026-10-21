"""Actual VFR PTS, native ROI pixels, neighbors and lifecycle integration."""
from fractions import Fraction
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from tools.test_local_editor import SCRIPTS
from local_media import run, prepare_media
from precision_evidence import extract
from stage_cache import Stage, save, load


@unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
class PrecisionTests(unittest.TestCase):
    def test_native_vfr_roi_and_neighbors_survive_key_evidence_promotion(self):
        import av
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'vfr.mkv'
            run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=30',
                 '-vf',"select='not(eq(mod(n,5),1))'",'-t','2','-fps_mode','vfr','-c:v','ffv1',source])
            asset=prepare_media(source,root/'proxy.mp4',width=160)
            out=root/'contact';result=extract(asset,.31,.51,out,'contact',[40,30,71,53])
            self.assertTrue(all(result['bracketing'].values()))
            self.assertEqual(result['sourceSize'],[320,180]);self.assertEqual(result['sourceToImageScale'],[1,1])
            frames={}
            with av.open(str(source)) as c:
                for frame in c.decode(video=0):frames[frame.pts]=frame.to_image().crop((40,30,111,83)).tobytes()
            for record in result['records']:
                image=Image.open(out/record['image'])
                self.assertEqual(image.size,(71,53));self.assertEqual(image.tobytes(),frames[record['pts']])
                self.assertEqual(Fraction(record['sourceSeconds']),record['pts']*Fraction(record['timeBase']))
            pts=[Fraction(r['sourceSeconds']) for r in result['records']]
            self.assertGreater(len(set(b-a for a,b in zip(pts,pts[1:]))),1)
            stage=Stage(out/'.stage-cache'/result['stageId']);keep=[result['records'][0]['artifact'],result['records'][-1]['artifact']]
            obs=out/'observations.json';save(obs,dict(stageId=result['stageId'],reviewed=True,observations=['Event bracket retained'],adopted=True,essentialArtifacts=keep))
            outcome=stage.finish(obs);self.assertEqual(outcome['state'],'cleaned')
            saved=load(out/'evidence.json')
            self.assertEqual([r['pts'] for r in saved['records']],[r['pts'] for r in result['records']])
            self.assertTrue(Path(saved['records'][0]['image']).is_file());self.assertIsNone(saved['records'][1]['image'])
            self.assertEqual(saved['crop'],[40,30,71,53])

    def test_navigation_helper_rejects_precision_purpose(self):
        from source_inspect import sample
        with self.assertRaisesRegex(ValueError,'Precision'):sample('unused',0,1,'unused',purpose='line')


if __name__=='__main__':unittest.main()
