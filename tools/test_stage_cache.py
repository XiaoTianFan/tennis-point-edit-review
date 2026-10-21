"""Stage cleanup safety, evidence promotion and interruption recovery."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.test_local_editor import SCRIPTS
from stage_cache import Stage, save, load, digest


class StageTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.stage=Stage.create(self.root,'contact')
        buffer=io.BytesIO();Image.new('RGB',(32,24),(13,31,78)).save(buffer,format='PNG')
        self.pixels=buffer.getvalue()
        self.a=self.stage.put('roi-a.png',self.pixels);self.b=self.stage.put('roi-b.png',self.pixels)
        self.index=self.root/'evidence.json'
        save(self.index,dict(records=[dict(pts=17,timeBase='1/60000',image=self.a),dict(pts=18,timeBase='1/60000',image=self.b)],crop=[1,2,32,24]))
        self.stage.index(self.index)
        self.obs=self.root/'observations.json'
        save(self.obs,dict(stageId=self.stage.owner['stageId'],reviewed=True,observations=['Contact bracket remains uncertain'],essentialArtifacts=['roi-a.png'],adopted=True))
        self.canonical=self.root/'shots.json';save(self.canonical,dict(points=[1,2],trajectory=[[.1,20,30]],uncertainty=.01))
        self.before=digest(self.canonical)

    def test_promotes_then_deletes_only_owned_images_and_keeps_numeric_data(self):
        extra=self.stage.root/'data'/'unregistered.png';extra.write_bytes(self.pixels)
        outcome=self.stage.finish(self.obs)
        self.assertEqual(outcome['state'],'cleaned')
        self.assertTrue(extra.exists())
        self.assertEqual(digest(self.canonical),self.before)
        records=load(self.index)['records']
        self.assertTrue(Path(records[0]['image']).is_file());self.assertIsNone(records[1]['image'])
        self.assertEqual([r['pts'] for r in records],[17,18])
        self.assertEqual(load(self.index)['crop'],[1,2,32,24])
        self.assertFalse((self.root/self.a).exists());self.assertFalse((self.root/self.b).exists())
        self.assertEqual(self.stage.finish(),outcome)

    def test_requires_readback_persisted_observations_and_key_evidence(self):
        for changes in [dict(reviewed=False),dict(observations=[]),dict(essentialArtifacts=[]),dict(essentialArtifacts=['foreign.png'])]:
            original=load(self.obs);save(self.obs,{**original,**changes})
            with self.assertRaises(ValueError):self.stage.finish(self.obs)
            self.assertTrue((self.root/self.a).exists());save(self.obs,original)

    def test_dangling_reference_changed_image_and_changed_catalog_fail_closed(self):
        dangling=self.root/'decision.json';save(dangling,dict(keyImage=str(self.root/self.a)))
        with self.assertRaisesRegex(ValueError,'still references'):self.stage.finish(self.obs)
        self.assertTrue((self.root/self.a).exists());dangling.unlink()
        (self.root/self.b).write_bytes(self.pixels+b'x')
        with self.assertRaisesRegex(ValueError,'Changed file'):self.stage.finish(self.obs)
        self.assertTrue((self.root/self.a).exists())

    def test_resume_after_unlink_before_receipt(self):
        unlink=Path.unlink;calls=[]
        def interrupted(path,*args,**kwargs):
            result=unlink(path,*args,**kwargs)
            calls.append(path)
            if len(calls)==1:raise InterruptedError('Synthetic stop after unlink')
            return result
        with patch.object(Path,'unlink',interrupted),self.assertRaises(InterruptedError):self.stage.finish(self.obs)
        self.assertTrue((self.root/self.b).exists())
        outcome=Stage(self.stage.root).finish()
        self.assertEqual(outcome['state'],'cleaned')
        self.assertTrue(Path(load(self.index)['records'][0]['image']).is_file())
        self.assertEqual(digest(self.canonical),self.before)

    def test_protected_data_change_blocks_resume_and_plan_is_fenced(self):
        with patch.object(Path,'unlink',side_effect=InterruptedError('stop')),self.assertRaises(InterruptedError):self.stage.finish(self.obs)
        save(self.canonical,dict(changed=True))
        with self.assertRaisesRegex(ValueError,'Changed file'):Stage(self.stage.root).finish()
        self.assertTrue((self.root/self.a).exists())
        plan=self.stage.root/'cleanup-plan.json';data=load(plan);data['protected']={};save(plan,data)
        with self.assertRaisesRegex(ValueError,'plan changed'):Stage(self.stage.root).finish()

    def test_refuses_paths_hardlinks_and_nonimages(self):
        for name in ('../source.png','project.json','nested/roi.png'):
            with self.assertRaises(ValueError):self.stage.put(name,self.pixels)
        with self.assertRaises(Exception):self.stage.put('fake.png',b'canonical records')
        alias=self.root/'hardlink.png'
        try:os.link(self.root/self.a,alias)
        except OSError:self.skipTest('Hardlinks unavailable')
        with self.assertRaisesRegex(ValueError,'Hardlinked'):self.stage.finish(self.obs)
        self.assertTrue(alias.exists())

    def test_refuses_symlink_ancestor(self):
        alias=self.root/'alias'
        try:alias.symlink_to(self.root,target_is_directory=True)
        except OSError:
            if os.name!='nt':raise
            import subprocess
            subprocess.run(['cmd','/c','mklink','/J',str(alias),str(self.root)],capture_output=True,check=True)
        try:
            with self.assertRaisesRegex(ValueError,'reparse'):Stage.create(alias,'navigation')
            with self.assertRaisesRegex(ValueError,'reparse'):self.stage.finish(self.obs)
        finally:
            # Only this test's verified link, never its target or a recursive tree.
            self.assertEqual(alias.parent,self.root)
            if alias.is_symlink():alias.unlink()
            else:
                self.assertTrue(alias.lstat().st_file_attributes & 0x400)
                os.rmdir(alias)


if __name__=='__main__':unittest.main()
