"""Appearance remains an optional observation with independent recovery fences."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/tennis-point-edit-review/scripts'))
import cv_appearance
import cv_players
import cv_stream
import test_cv_stream as stream_fixtures
from test_cv_players import SyntheticPlayers


class AppearanceContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = self.root/'architecture.py'; self.module.write_text('# local fixture')
        self.weights = self.root/'weights.pt'; self.weights.write_bytes(b'fixture')

    def config(self, **values):
        return dict(module=str(self.module), weights=str(self.weights), **values)

    def test_sampling_requires_coincident_person_observations(self):
        c = cv_appearance.configuration(self.config(stride=30), 6)
        self.assertEqual(c['device'], 'cpu')
        for value in [self.config(stride=5), self.config(stride=True), self.config(batchSize=65),
                      self.config(device='auto'), self.config(overlayMasks=[[0, 0, 0, 2]])]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                cv_appearance.configuration(value, 6)

    def test_native_crop_rounding_clipping_and_empty_evidence(self):
        self.assertEqual(cv_appearance.crop_box([-1.2, 1.3, 3.1, 9.7], 8, 6), [0, 1, 4, 6])
        self.assertIsNone(cv_appearance.crop_box([10, 0, 12, 5], 8, 6))
        self.assertIsNone(cv_appearance.crop_box([4, 1, 2, 4], 8, 6))
        with self.assertRaises(ValueError):
            cv_appearance.crop_box([0, float('nan'), 5, 5], 8, 6)

    def test_full_precision_is_local_and_restores_flags_after_failure(self):
        cudnn = SimpleNamespace(allow_tf32=True)
        matmul = SimpleNamespace(allow_tf32=True)
        torch = SimpleNamespace(backends=SimpleNamespace(cudnn=cudnn, cuda=SimpleNamespace(matmul=matmul)),
                                inference_mode=nullcontext)
        with self.assertRaisesRegex(RuntimeError, 'model failed'):
            with cv_appearance.fp32_execution(torch, 'cuda'):
                self.assertFalse(cudnn.allow_tf32)
                self.assertFalse(matmul.allow_tf32)
                raise RuntimeError('model failed')
        self.assertTrue(cudnn.allow_tf32)
        self.assertTrue(matmul.allow_tf32)
        with cv_appearance.fp32_execution(torch, 'cpu'):
            self.assertTrue(cudnn.allow_tf32)
            self.assertTrue(matmul.allow_tf32)

    def test_appearance_sampling_reuses_rgb_and_does_not_assign_identity(self):
        calls = []
        class Frame:
            def __init__(self): self.conversions = 0
            def to_ndarray(self, *, format):
                self.conversions += 1
                return np.full((8, 8, 3), 7, np.uint8)
        class Encoder:
            def annotate(self, rgb, detections):
                calls.append((int(rgb.sum()), len(detections)))
                for d in detections: d['appearance'] = dict(status='observed', adopted=False)
        players = object.__new__(cv_players.Players)
        players.c = dict(stride=2, crops=[None, [0, 0, 4, 4]], appearance=dict(stride=4))
        players.appearance = Encoder(); players.metrics = dict(sampledFrames=0, detections=0)
        players.detect = lambda rgb, crop, view, frame_id: ([dict(id=f'{frame_id}-{view}', box=[0, 0, 4, 4], playerId=None)], 0)
        frames = [Frame() for _ in range(5)]
        observed = list(players.annotate((dict(id=f'F{i}'), frame) for i, frame in enumerate(frames)))
        self.assertEqual([r['playerObservations']['appearanceSampled'] for r, _ in observed], [True, False, False, False, True])
        self.assertEqual(calls, [(1344, 2), (1344, 2)])
        for i, (row, shared) in enumerate(observed):
            if i % 2 == 0:
                shared.to_ndarray(format='rgb24')
                self.assertEqual(frames[i].conversions, 1)
                for d in row['playerObservations']['detections']: self.assertIsNone(d['playerId'])
        self.assertIsNone(observed[2][0]['playerObservations']['detections'][0]['appearance'])


class AppearanceRecovery(unittest.TestCase):
    setUp = stream_fixtures.StreamContract.setUp

    def test_changed_appearance_files_block_resume_before_backend_load(self):
        appearance = {}
        for key in ('module', 'weights'):
            p = self.root/('appearance-'+key); p.write_text('original'); appearance[key] = str(p)
        self.config['players'] = dict(weights=self.config['weights'], architecture=self.config['modelConfig'],
                                      stride=5, appearance=dict(appearance, stride=10))
        for key in ('module', 'weights'):
            with self.subTest(key=key):
                for path in appearance.values(): Path(path).write_text('original')
                target = self.root/('run-'+key)
                with patch.object(cv_stream, 'WASB', stream_fixtures.SyntheticDetector), patch.object(cv_stream, 'Players', SyntheticPlayers):
                    cv_stream.scan(self.source, target, self.config, stop_after_chunks=1)
                Path(appearance[key]).write_text('changed')
                with patch.object(cv_stream, 'WASB') as backend, self.assertRaisesRegex(ValueError, 'changed'):
                    cv_stream.scan(self.source, target, self.config, resume=True)
                backend.assert_not_called()
                self.assertFalse((target/'result.json').exists())


if __name__ == '__main__':
    unittest.main()
