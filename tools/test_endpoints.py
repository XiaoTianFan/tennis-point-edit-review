"""Ending evidence cannot certify an excluded event or a changed clip."""
import copy
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from tools.test_local_editor import SCRIPTS
from endpoint_audit import audit, template


def fixture():
    p = dict(fps='60000/1001', assets=[dict(id='src', frames=1200,
        sourceIdentity=dict(sha256='a'*64), sourceMapping=dict(schema='original-pts-grid/v1',
        originSeconds='5', timeBase='1/90000'))], clips=[dict(id='c1', assetId='src',
        pointId='P001', inFrame=0, outFrame=600)])
    d = template(p)
    d['records'][0].update(status='verified',
        anchor=dict(kind='next_serve', sourceSeconds='20', relation='unknown'),
        lastLiveSeconds='14', endWindowSeconds=['14.2', '14.3'], retainThroughSeconds='14.8',
        forwardWindowSeconds=['13.5', '16'], continuationFound=False,
        reason='Synthetic first dead-ball bracket and retained reaction', evidence=['observations.json'])
    return p, d


class EndpointTests(unittest.TestCase):
    def test_template_is_pending_and_every_clip_is_required(self):
        p, d = fixture()
        self.assertFalse(audit(p, template(p))['checksPassed'])
        p['clips'].append(dict(id='c2', assetId='src', pointId='P001', inFrame=700, outFrame=800))
        self.assertFalse(audit(p, d)['checksPassed'])
        p['clips'].pop(); d['records'].append(copy.deepcopy(d['records'][0]))
        self.assertFalse(audit(p, d)['checksPassed'])

    def test_native_clock_and_exclusive_out_frame(self):
        p, d = fixture(); self.assertTrue(audit(p, d)['complete'])
        r = d['records'][0]; cut = Fraction(5) + Fraction(600) / Fraction(p['fps'])
        r.update(endWindowSeconds=[str(cut), str(cut)], retainThroughSeconds=str(cut))
        self.assertFalse(audit(p, d)['checksPassed'])
        p['clips'][0]['outFrame'] += 1; r['binding']['outFrame'] += 1
        self.assertTrue(audit(p, d)['complete'])

    def test_forward_inspection_must_extend_past_cut_and_cover_live_play(self):
        for field, value in [('forwardWindowSeconds', ['14.1', '16']),
                             ('forwardWindowSeconds', ['13', '15.01']),
                             ('continuationFound', True), ('continuationFound', None)]:
            p, d = fixture(); d['records'][0][field] = value
            with self.subTest(field=field, value=value): self.assertFalse(audit(p, d)['checksPassed'])

    def test_stale_cut_source_and_rate_are_rejected(self):
        for mutate in [lambda p: p['clips'][0].update(outFrame=601),
                       lambda p: p['clips'][0].update(inFrame=1), lambda p: p.update(fps='60'),
                       lambda p: p['assets'][0]['sourceMapping'].update(originSeconds='0'),
                       lambda p: p['assets'][0]['sourceIdentity'].update(sha256='b'*64)]:
            p, d = fixture(); mutate(p); self.assertFalse(audit(p, d)['checksPassed'])

    def test_next_serve_can_be_same_point_without_winner_or_score(self):
        p, d = fixture(); d['records'][0]['anchor']['relation'] = 'same_point'
        self.assertTrue(audit(p, d)['complete'])
        d['records'][0]['anchor'].pop('relation'); self.assertFalse(audit(p, d)['checksPassed'])

    def test_uncertain_and_truncated_endings_are_never_complete(self):
        p, d = fixture(); r = d['records'][0]
        r.update(status='uncertain', endWindowSeconds=None, cessationObserved=True)
        result = audit(p, d)
        self.assertTrue(result['checksPassed']); self.assertFalse(result['complete'])
        r['cessationObserved'] = False; self.assertFalse(audit(p, d)['checksPassed'])
        p['clips'][0]['outFrame'] = 1200; r['binding']['outFrame'] = 1200
        end = str(Fraction(5) + Fraction(1200) / Fraction(p['fps']))
        r.update(status='source_truncated', anchor=dict(kind='recording_end', sourceSeconds=end,
            reason='Recording ends before terminal event'), forwardWindowSeconds=['13', end])
        r['lastLiveSeconds'] = r['retainThroughSeconds'] = str(Fraction(end) - 1/Fraction(p['fps']))
        self.assertTrue(audit(p, d)['checksPassed']); self.assertFalse(audit(p, d)['complete'])
        p['clips'][0]['outFrame'] -= 1; r['binding']['outFrame'] -= 1
        self.assertFalse(audit(p, d)['checksPassed'])

    def test_bounded_proxy_is_not_recording_end(self):
        p, d = fixture(); r = d['records'][0]
        p['assets'][0]['sourceProbe'] = dict(format=dict(start_time='5', duration='60'))
        r['anchor'] = dict(kind='recording_end', sourceSeconds='25.02', reason='No next serve')
        self.assertFalse(audit(p, d)['checksPassed'])

    def test_missing_evidence_files_fail_cli_equivalent_check(self):
        p, d = fixture()
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(audit(p, d, directory)['checksPassed'])
            (Path(directory) / 'observations.json').write_text('{}', encoding='utf-8')
            self.assertTrue(audit(p, d, directory)['complete'])

    def test_bad_timestamps_cannot_pass(self):
        for value in [None, True, 'NaN', '1/0', 'wrong-clock']:
            p, d = fixture(); d['records'][0]['retainThroughSeconds'] = value
            self.assertFalse(audit(p, d)['checksPassed'])


if __name__ == '__main__': unittest.main()
