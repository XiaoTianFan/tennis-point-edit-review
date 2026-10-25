"""Full-stream coverage and recovery contracts use a synthetic VFR video."""
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import av
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/tennis-point-edit-review/scripts'))
import cv_stream
from cv_wasb import configuration


class SyntheticDetector:
    def __init__(self, config):
        self.provenance={'backend':'synthetic-contract-test'}
        self.metrics={}

    def observe(self, frames):
        for row, frame in frames:
            row['modelCandidates']=[dict(value=int(frame.to_ndarray(format='gray').sum()))]
            yield row


class InterruptingDetector(SyntheticDetector):
    def observe(self, frames):
        for i,row in enumerate(super().observe(frames)):
            if i==16:raise RuntimeError('Synthetic interrupted second chunk')
            yield row


class StreamContract(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source.mkv'
        with av.open(str(self.source),'w') as con:
            stream=con.add_stream('ffv1',rate=30);stream.width=64;stream.height=48
            stream.pix_fmt='yuv420p';stream.time_base=Fraction(1,1000)
            stream.codec_context.time_base=Fraction(1,1000)
            pts=100
            for i in range(23):
                frame=av.VideoFrame.from_ndarray(np.full((48,64,3),i*9,dtype='uint8'),format='rgb24')
                frame.pts=pts;frame.time_base=Fraction(1,1000);pts += [33,42,34][i%3]
                for packet in stream.encode(frame):con.mux(packet)
            for packet in stream.encode():con.mux(packet)
        self.config=dict(batch=4,chunkFrames=12,maxFrames=100)
        for name in ('module','modelConfig','weights'):
            path=self.root/name;path.write_text('synthetic fixture')
            self.config[name]=str(path)

    def scan(self, target, **kwargs):
        with patch.object(cv_stream,'WASB',SyntheticDetector):
            return cv_stream.scan(self.source,self.root/target,self.config,**kwargs)

    def rows(self,target):
        run=self.root/target;result=cv_stream.read(run/'result.json')
        return [json.loads(line) for c in result['chunks'] for line in (run/'chunks'/c['file']).read_text().splitlines()]

    def test_checkpoint_resume_preserves_every_nonzero_vfr_pts_once(self):
        self.scan('whole')
        checkpoint=self.scan('resume',stop_after_chunks=1)
        self.assertEqual(checkpoint['status'],'checkpointed');self.assertEqual(checkpoint['frames'],12)
        self.assertFalse((self.root/'resume/result.json').exists())
        result=self.scan('resume',resume=True)
        self.assertEqual(result['coverage']['frames'],23)
        self.assertEqual(self.rows('whole'),self.rows('resume'))
        times=[Fraction(r['seconds']) for r in self.rows('resume')]
        self.assertGreater(times[0],0);self.assertGreater(len(set(b-a for a,b in zip(times,times[1:]))),1)
        self.assertEqual(self.scan('resume',resume=True),result)

    def test_interrupted_uncommitted_work_and_orphan_do_not_duplicate_frames(self):
        with patch.object(cv_stream,'WASB',InterruptingDetector),self.assertRaisesRegex(RuntimeError,'interrupted'):
            cv_stream.scan(self.source,self.root/'run',self.config)
        state=cv_stream.read(self.root/'run/state.json');self.assertEqual(state['frames'],12)
        (self.root/'run/chunks/orphan.jsonl').write_text('unfinished work')
        self.scan('run',resume=True);self.scan('whole')
        self.assertEqual(self.rows('run'),self.rows('whole'))
        self.assertTrue((self.root/'run/chunks/orphan.jsonl').exists())

    def test_changed_observations_fail_closed(self):
        self.scan('run',stop_after_chunks=1)
        state=cv_stream.read(self.root/'run/state.json')
        (self.root/'run/chunks'/state['chunks'][0]['file']).write_text('{}\n')
        with self.assertRaisesRegex(ValueError,'chunk changed'):self.scan('run',resume=True)

    def test_source_config_and_weight_changes_cannot_mix_with_committed_work(self):
        self.scan('run',stop_after_chunks=1)
        self.config['threshold']=.4
        with self.assertRaisesRegex(ValueError,'changed'):self.scan('run',resume=True)
        del self.config['threshold']
        weight=Path(self.config['weights']);weight.write_text('different fixture weights')
        with self.assertRaisesRegex(ValueError,'changed'):self.scan('run',resume=True)
        self.assertFalse((self.root/'run/result.json').exists())
        self.scan('new',stop_after_chunks=1)
        with self.source.open('ab') as f:f.write(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.scan('new',resume=True)

    def test_bad_chunk_alignment_and_implicit_resume_rejected(self):
        with self.assertRaises(ValueError):configuration({**self.config,'chunkFrames':13})
        with self.assertRaises(ValueError):configuration({**self.config,'crops':[[0,0,-1,10]]})
        self.scan('run',stop_after_chunks=1)
        with self.assertRaisesRegex(ValueError,'explicit resume'):self.scan('run')


if __name__=='__main__':unittest.main()
