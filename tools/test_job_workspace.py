"""Durable defaults, explicit directories and immutable relocation regressions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/tennis-point-edit-review/scripts'
sys.path.insert(0, str(SCRIPTS))
from job_workspace import create_workspace, outputs_root, read_document, relocation_map, resolve_reference
from local_model import Store
from test_local_editor import sample


class WorkspaceTests(unittest.TestCase):
    def test_primary_checkout_used_from_linked_worktree(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"TENNIS_OUTPUTS_ROOT":""}):
            root = Path(temp)/'saved'; root.mkdir()
            def git(*args):
                return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True)
            git('init')
            package = root/'skills/tennis-point-edit-review'; package.mkdir(parents=True)
            (package/'SKILL.md').write_text('synthetic skill')
            git('add','.')
            git('-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-m','fixture')
            worktree = Path(temp)/'disposable'
            git('worktree','add','--detach',str(worktree))
            self.assertEqual(outputs_root(package=worktree/'skills/tennis-point-edit-review'),root/'outputs')

    def test_explicit_work_dir_wins_and_collision_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            record=create_workspace(work_dir=base/'chosen',root=base/'ignored')
            self.assertEqual(record['directory'],str(base/'chosen'))
            self.assertFalse(Path(record['paths']['edit']).exists())
            with self.assertRaises(ValueError):create_workspace(work_dir=base/'chosen')
            one=create_workspace(source='synthetic.mov',root=base/'outputs')
            two=create_workspace(source='synthetic.mov',root=base/'outputs')
            self.assertNotEqual(one['directory'],two['directory'])
            with self.assertRaises(ValueError):create_workspace(root=base/'outputs',job_id='../escape')
            with self.assertRaises(ValueError):create_workspace(root=base/'outputs',job_id='CON')

    def test_detached_package_has_no_cwd_fallback(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"TENNIS_OUTPUTS_ROOT":""}):
            with self.assertRaises(ValueError):outputs_root(package=Path(temp))
            with self.assertRaises(ValueError):outputs_root('relative')
            with patch.dict(os.environ, {'TENNIS_OUTPUTS_ROOT':temp}):self.assertEqual(outputs_root(),Path(temp))

    def test_relocation_reopens_without_rewriting_history_or_match_state(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp); old=base/'old';old.mkdir();job=base/'job';job.mkdir();new=job/'work';new.mkdir()
            project=sample(old);project['overlays']=[]
            project['undo']=[{'clips':project['clips'],'overlays':[{'image':str(old/'overlay.png')}]}]
            original=json.dumps(project).encode()
            (new/'project.json').write_bytes(original)
            (old/'source.mp4').rename(new/'source.mp4');old.rmdir()
            (job/'relocation-map.json').write_text(json.dumps(dict(schema='tennis-job-relocation/v1',mappings=[dict(old=str(old),new=str(new))])))
            loaded=Store(new).get()
            self.assertEqual(loaded['assets'][0]['path'],str(new/'source.mp4'))
            self.assertEqual(loaded['undo'][0]['overlays'][0]['image'],str(new/'overlay.png'))
            for key in ('revision','clips','review','answers'):
                self.assertEqual(loaded[key],project[key])
            self.assertEqual((new/'project.json').read_bytes(),original)
            self.assertEqual(read_document(old/'project.json',job),loaded)
            mapping=relocation_map(job)
            self.assertEqual(resolve_reference(str(base/'old-other/file'),mapping),str(base/'old-other/file'))
            self.assertEqual(resolve_reference('Note: '+str(old/'source.mp4'),mapping),'Note: '+str(old/'source.mp4'))
            nested=[dict(old=str(old),new=str(new)),dict(old=str(old/'sub'),new=str(job/'nested'))]
            self.assertEqual(resolve_reference(str(old/'sub/a'),nested),str(job/'nested/a'))

    def test_mapping_cannot_escape_job(self):
        with tempfile.TemporaryDirectory() as temp:
            job=Path(temp)/'job';job.mkdir()
            (job/'relocation-map.json').write_text(json.dumps(dict(schema='tennis-job-relocation/v1',mappings=[dict(old=str(Path(temp)/'old'),new=str(Path(temp)/'outside'))])))
            with self.assertRaises(ValueError):relocation_map(job)


if __name__=='__main__':unittest.main()
