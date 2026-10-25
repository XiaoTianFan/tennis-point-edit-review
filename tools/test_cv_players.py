"""Independent person observations share decoding and survive stream recovery."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/tennis-point-edit-review/scripts'))
import cv_players
import cv_stream
import test_cv_stream as fixtures


class SyntheticPlayers:
    def __init__(self, config, cache_directory):
        self.c=config;self.provenance={'backend':'synthetic-players','device':config['device']}
        self.metrics=dict(sampledFrames=0)

    def annotate(self, frames):
        for row, frame in frames:
            sampled=int(row['id'][1:])%self.c['stride']==0
            row['playerObservations']=dict(sampled=sampled,
                detections=[dict(playerId=None,side='unknown',value=int(frame.to_ndarray(format='gray').sum()))] if sampled else [])
            self.metrics['sampledFrames']+=int(sampled)
            yield row,frame


class PlayerStreamContract(unittest.TestCase):
    setUp=fixtures.StreamContract.setUp
    rows=fixtures.StreamContract.rows

    def prepare(self):
        # The existing stream fixture stores its configuration on this instance.
        self.config_data=self.config
        self.config={**self.config_data,'players':dict(weights=self.config_data['weights'],
            architecture=self.config_data['modelConfig'],stride=5)}

    def scan(self,target,**kwargs):
        with patch.object(cv_stream,'WASB',fixtures.SyntheticDetector),patch.object(cv_stream,'Players',SyntheticPlayers):
            return cv_stream.scan(self.source,self.root/target,self.config,**kwargs)

    def test_shared_frame_rgb_conversion_is_reused_without_changing_pixels(self):
        class Frame:
            width=4
            def __init__(self):self.calls=0
            def to_ndarray(self,format):
                self.calls+=1;return np.full((3,4,3),9,np.uint8)
        original=Frame();shared=cv_players.SharedFrame(original)
        a=shared.to_ndarray(format='rgb24');b=shared.to_ndarray(format='rgb24')
        self.assertIs(a,b);self.assertEqual(original.calls,1);self.assertEqual(shared.width,4)
        self.assertEqual(a.sum(),324)

    def test_player_sampling_and_unknown_identity_survive_checkpoint_resume(self):
        self.prepare();self.scan('whole');self.scan('resumed',stop_after_chunks=1);result=self.scan('resumed',resume=True)
        whole=self.rows('whole');rows=self.rows('resumed');self.assertEqual(rows,whole)
        sampled=[i for i,r in enumerate(rows) if r['playerObservations']['sampled']]
        self.assertEqual(sampled,[0,5,10,15,20]);self.assertEqual(len(rows),23)
        for row in rows:
            person=row['playerObservations']
            if person['sampled']:
                self.assertEqual(person['detections'][0]['value'],row['modelCandidates'][0]['value'])
                self.assertIsNone(person['detections'][0]['playerId'])
        self.assertEqual(result['adjudications'],[]);self.assertIsNone(result['statistics'])

    def test_player_config_and_external_binding_cannot_change_during_resume(self):
        self.prepare();self.scan('run',stop_after_chunks=1);self.config['players']['stride']=6
        with self.assertRaisesRegex(ValueError,'changed'):self.scan('run',resume=True)
        self.config['players']['stride']=5
        Path(self.config['players']['architecture']).write_text('modified architecture')
        with self.assertRaisesRegex(ValueError,'changed'):self.scan('run',resume=True)
        self.assertFalse((self.root/'run/result.json').exists())


if __name__=='__main__':unittest.main()
