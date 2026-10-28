import copy
import json
import tempfile
import unittest
from pathlib import Path

from cv_temporal_evaluate import compare, digest, run


def fixture(times, intervals):
    predictions = dict(status='complete',windows=[dict(windowId='segment',candidates=[
        dict(frame=100+i,seconds=t,view=i%2) for i,t in enumerate(times)])])
    reference = dict(segmentIds=['segment'],sourceIdentity=dict(sha256='source'),
        events=[dict(id=f'r{i}',segmentId='segment',event='racket_contact',
                     frameBracket=[100+i,100+i],intervalSeconds=v) for i,v in enumerate(intervals)],
        unknowns=[],observableIntervals=[])
    windows = dict(sourceSha256='source',windows=[dict(id='segment',startFrame=0,endFrameExclusive=1000)])
    return predictions,reference,windows


class TemporalEvaluationTest(unittest.TestCase):
    def test_maximum_matching_does_not_lose_event_to_greedy_nearest(self):
        p,r,w = fixture(['10.02','10.08'],[['10','10'],['10.04','10.04']])
        result = compare(p,r,w)
        self.assertEqual(result['counts']['matched_timing'],2)
        self.assertEqual(len({m['referenceId'] for m in result['matches']}),2)

    def test_duplicate_unknown_unread_and_false_are_separate(self):
        p,r,w = fixture(['10','10.01','11','12','13'],[['10','10']])
        r['unknowns']=[dict(segmentId='segment',intervalSeconds=['11','11'])]
        r['observableIntervals']=[dict(segmentId='segment',intervalSeconds=['9','11']),
                                  dict(segmentId='segment',intervalSeconds=['12','12'])]
        result=compare(p,r,w)
        self.assertEqual([c['status'] for c in result['candidates']],
                         ['matched_timing','duplicate_collision_candidate','unresolved_reference',
                          'false_collision_candidate','not_adjudicated'])
        self.assertEqual(result['knownEventTimingRecall'],1)
        self.assertEqual(result['adjudicatedCandidateTimingPrecision'],1/3)
        self.assertIsNone(result['allCandidatePrecision'])
        self.assertIsNone(result['semanticAccuracy'])
        self.assertFalse(result['productionAccepted'])

    def test_zero_reference_is_not_perfect_recall(self):
        p,r,w=fixture([],[])
        result=compare(p,r,w)
        self.assertIsNone(result['knownEventTimingRecall'])
        self.assertIsNone(result['allCandidatePrecision'])

    def test_outside_window_reference_is_still_a_miss(self):
        p,r,w=fixture([], [['10','10'],['11','11']])
        r['events'][1]['frameBracket']=[1000,1002]
        result=compare(p,r,w)
        self.assertEqual(result['counts']['missed'],2)
        self.assertEqual(result['counts']['outsideWindowMisses'],1)
        self.assertEqual(result['knownEventTimingRecall'],0)

    def test_fractional_frame_timing_does_not_round_into_tolerance(self):
        p,r,w=fixture(['1001/20000'], [['0','0']])
        self.assertEqual(compare(p,r,w)['counts']['matched_timing'],0)
        p['windows'][0]['candidates'][0]['seconds']='1/20'
        self.assertEqual(compare(p,r,w)['counts']['matched_timing'],1)

    def test_scope_source_ids_and_pts_are_checked(self):
        p,r,w=fixture(['1'],[['1','1']])
        wrong=copy.deepcopy(w);wrong['sourceSha256']='different'
        with self.assertRaisesRegex(ValueError,'Source identity'):
            compare(p,r,wrong)
        wrong=copy.deepcopy(p);wrong['windows'].append(wrong['windows'][0])
        with self.assertRaisesRegex(ValueError,'Duplicate window'):
            compare(wrong,r,w)
        p['windows'][0]['candidates'][0].update(pts=2,timeBase='1/1')
        with self.assertRaisesRegex(ValueError,'source PTS'):
            compare(p,r,w)
        p['windows'][0]['candidates'][0]['pts']=1
        r['events'][0]['sourceFrames']=[dict(ordinal=100,pts=2,timeBase='1/1')]*2
        with self.assertRaisesRegex(ValueError,'source PTS'):
            compare(p,r,w)

    def test_cli_checks_frozen_bytes_and_never_overwrites_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            p,r,w=fixture(['1'],[['1','1']])
            def save(name,value):
                path=root/name;path.write_text(json.dumps(value),encoding='utf-8');return path
            raw=save('predictions.json',p)
            windows=save('windows.json',w)
            save('manifest.json',dict(windows=dict(sha256=digest(windows)),sourceIdentity=dict(sha256='source')))
            r['priorPredictions']=dict(sha256=digest(raw))
            reference=save('reference.json',r)
            output=root/'result.json'
            run(root,reference,windows,output)
            original=output.read_bytes()
            with self.assertRaises(FileExistsError):
                run(root,reference,windows,output)
            self.assertEqual(original,output.read_bytes())
            raw.write_text(raw.read_text()+'\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Predictions changed'):
                run(root,reference,windows,root/'second.json')


if __name__=='__main__':
    unittest.main()
