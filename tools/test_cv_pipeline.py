"""Changed-contract tests for opt-in vision and rendered-reference mapping."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/tennis-point-edit-review/scripts'))
from cv_pipeline import infer_events, make_plan, settings
from cv_reference import map_label, render_mapping
from cv_observations import fit_court, ground_hypothesis, select_track
from cv_evaluate import compare
from media_probe import identity
from local_model import write


class VisionContract(unittest.TestCase):
    def test_comparison_keeps_nulls_and_fences_clock_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);rows=[dict(seconds='1/2',modelCandidates=[],colourCandidates=[],track=None)]
            (d/'observations.jsonl').write_text(json.dumps(rows[0])+'\n',encoding='utf-8')
            run=dict(schema='tennis-vision-observations/v1',status='complete',runId='synthetic',
                     sourceIdentity={'sha256':'a'},backend={'backend':'classical'},metrics={},
                     observationsSha256=identity(d/'observations.jsonl')['sha256'])
            write(d/'result.json',run)
            ref=dict(sourceIdentity={'sha256':'a'},referenceKind='synthetic',points=[dict(pts=30,timeBase='1/60',x=1,y=2)])
            result=compare(d/'result.json',ref)
            self.assertIsNone(result['summary']['selectedError']['medianPixels'])
            self.assertEqual(result['summary']['selectedError']['nullCount'],1)
            ref['sourceIdentity']['sha256']='wrong'
            with self.assertRaises(ValueError):compare(d/'result.json',ref)
            ref['sourceIdentity']['sha256']='a';(d/'observations.jsonl').write_text('{}\n')
            with self.assertRaises(ValueError):compare(d/'result.json',ref)

    def test_gaps_and_seams_never_become_bounces(self):
        rows=[]
        for i,y in enumerate([0,4,8,12,8,4,0]):
            rows.append(dict(id=str(i),windowId=0,segmentId=0,track=dict(x=50,y=y),
                             seconds=str(Fraction(i,60)),pts=i,timeBase='1/60',nativeSize=[640,360],
                             court={'status':'abstained'},camera={'status':'stable_candidate'}))
        events=infer_events(rows)
        self.assertEqual(len(events),1)
        self.assertIsNone(events[0]['adjudication'])
        self.assertIsNone(events[0]['conditionalGround'])
        rows[1]['track']=None
        self.assertEqual(infer_events(rows),[])
        rows[1]['track']=dict(x=50,y=4);rows[4]['segmentId']=1
        self.assertEqual(infer_events(rows),[])

    def test_projection_is_conditional_and_requires_redundancy(self):
        image=[[0,0],[100,0],[0,200],[100,200],[0,100],[100,100]]
        ground=[[0,0],[10,0],[0,20],[10,20],[0,10],[10,10]]
        self.assertEqual(fit_court(image[:4],ground[:4])['status'],'abstained')
        h=fit_court(image,ground)
        p=ground_hypothesis(h,[50,100],2)
        self.assertAlmostEqual(p['x'],5)
        self.assertIn('not confidence interval',p['meaning'])

    def test_ambiguity_abstains(self):
        self.assertEqual(select_track([dict(x=0,y=0),dict(x=1,y=1)],None,.02,100)[0],None)
        self.assertEqual(select_track([dict(x=99,y=0)],dict(x=0,y=0),.02,100)[0],None)

    def test_court_rejects_discarded_contradictory_side(self):
        ground=[[0,0],[10,0],[0,10],[10,10],[0,20],[10,20],[5,0],[5,20]]
        image=[[x*10,y*10] for x,y in ground]
        image[1][0]+=1000; image[3][0]+=1000
        self.assertEqual(fit_court(image,ground)['status'],'abstained')

    def test_run_windows_and_limits(self):
        for value in [dict(windows=[[2,1]]),dict(windows=[[0,40]]),dict(windows=[[0,5],[4,8]]),dict(maxFrames=0),dict(backend='automatic_truth')]:
            with self.assertRaises(ValueError):settings(value)

    def test_handoff_source_clock_fence_and_no_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            result=dict(schema='tennis-vision-observations/v1',status='complete',runId='test',sourceIdentity={'sha256':'a'},
                        coverage=[dict(windowId=0,requested=['10','11'])],events=[])
            media=dict(sourceIdentity={'sha256':'a'},sourceMapping={'schema':'original-pts-grid/v1','originSeconds':'10'},fps='60',frames=60)
            for name,value in [('result',result),('media',media),('players',[{'id':'A','name':'Player A'},{'id':'B','name':'Player B'}])]:write(d/(name+'.json'),value)
            plan=make_plan(d/'result.json',d/'media.json',d/'players.json',d/'plan.json')
            self.assertEqual(plan['clips'][0]['inFrame'],0)
            self.assertEqual(plan['clips'][0]['outFrame'],60)
            self.assertEqual(plan['review']['rows'][0]['sourceRangesSeconds'],[[10.,11.]])
            self.assertEqual(plan['approval'],{})
            self.assertEqual(plan['review']['rows'][0]['initial'],{})
            self.assertTrue(plan['review']['provisionalPoints'])
            with self.assertRaises(ValueError):make_plan(d/'result.json',d/'media.json',d/'players.json',d/'plan.json')
            media['sourceIdentity']['sha256']='other';write(d/'media.json',media)
            with self.assertRaises(ValueError):make_plan(d/'result.json',d/'media.json',d/'players.json',d/'new.json')


class RenderReferences(unittest.TestCase):
    def fixture(self):
        p=dict(revision=4,fps='60',assets=[dict(id='src',sourceMapping={'originSeconds':'5'})],
               clips=[dict(id='a',assetId='src',pointId='P1',inFrame=60,outFrame=120),
                      dict(id='hold',assetId='src',inFrame=119,kind='hold',durationFrames=30),
                      dict(id='b',assetId='src',pointId='P2',inFrame=180,outFrame=240)])
        e=dict(state='complete',revision=4,frames=150,timelineFrames=150,
               settings={'fps':'60','clipIds':['a','hold','b']},ranges=[
                   dict(clipId='a',masterStartFrame=0,masterEndFrame=60,exportStartFrame=0,exportEndFrame=60),
                   dict(clipId='hold',masterStartFrame=60,masterEndFrame=90,exportStartFrame=60,exportEndFrame=90),
                   dict(clipId='b',masterStartFrame=90,masterEndFrame=150,exportStartFrame=90,exportEndFrame=150)])
        return p,e

    def test_trims_hold_origin_and_half_open_mapping(self):
        p,e=self.fixture();rows=render_mapping(p,e,150,'60')
        self.assertEqual(map_label(rows,'src','6.5')['occurrences'][0]['seconds'],'1/2')
        self.assertEqual(map_label(rows,'src','8.5')['occurrences'][0]['seconds'],'2')
        self.assertEqual(map_label(rows,'src','7')['status'],'not_retained_or_unknown_asset')
        self.assertIsNone(map_label(rows,'src','6.99',['6.98','7.01'])['occurrences'][0]['bracketSeconds'])

    def test_stale_revision_rate_length_fail(self):
        p,e=self.fixture()
        for args in [(150,'30'),(149,'60')]:
            with self.assertRaises(ValueError):render_mapping(p,e,*args)
        e['revision']=3
        with self.assertRaises(ValueError):render_mapping(p,e,150,'60')

    def test_ambiguous_legacy_origin_fails(self):
        p,e=self.fixture();p['assets'][0].pop('sourceMapping')
        with self.assertRaises(ValueError):render_mapping(p,e,150,'60')


if __name__=='__main__':unittest.main()
