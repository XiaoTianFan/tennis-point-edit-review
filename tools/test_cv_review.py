"""Source-clock, correction persistence and authority boundaries for event review."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/tennis-point-edit-review/scripts'))
from cv_review import make_plan
from local_model import SCHEMA, Store, Conflict, context, validate, write
from media_probe import identity


class EventReviewContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.source = self.root/'synthetic-source.bin'
        self.source.write_bytes(b'explicit synthetic source fixture')
        self.source_id = identity(self.source)
        run = self.root/'run'; (run/'chunks').mkdir(parents=True)
        rows = [dict(id=f'F{i:09}', pts=pts, timeBase='1/1000', seconds=seconds) for i,(pts,seconds) in enumerate([(100,'1/10'),(142,'71/500'),(176,'22/125')])]
        chunk = run/'chunks/test.jsonl'; chunk.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        stream = dict(schema='tennis-vision-stream/v1', status='complete', runId='synthetic', sourceIdentity=self.source_id,
                      coverage=dict(frames=3, firstSeconds='1/10', lastSeconds='22/125'),
                      chunks=[dict(file=chunk.name, sha256=identity(chunk)['sha256'], frames=3, firstSeconds='1/10', lastSeconds='22/125')])
        self.stream = run/'result.json'; write(self.stream,stream)
        self.proposal = dict(schema='tennis-vision-proposals/v1', status='complete', sourceIdentity=self.source_id, streamIdentity=identity(self.stream),
                             events=[dict(id='E1', kind='racket_contact', side='near', seconds='71/500', adjudication=None)])
        self.media = dict(sourceIdentity=self.source_id,sourceMapping=dict(schema='original-pts-grid/v1',originSeconds='1/10'),frames=3,fps='30',path=str(self.source))
        write(self.root/'proposals.json',self.proposal);write(self.root/'media.json',self.media)
        write(self.root/'players.json',[dict(id='A',name='Synthetic A'),dict(id='B',name='Synthetic B')])

    def plan(self):
        return make_plan(self.stream,self.root/'proposals.json',self.root/'media.json',self.root/'players.json',self.root/'plan.json')

    def project(self):
        p=self.plan();p.update(schema=SCHEMA,revision=0,fps='30',width=64,height=48,answers={},needsRebuild=[],undo=[],redo=[],events=[])
        p['assets']=[dict(self.media,id='vision-source')]
        return validate(p)

    def test_whole_source_preserved_and_vfr_pts_maps_without_point_adoption(self):
        p=self.project()
        self.assertEqual(p['clips'],[dict(id='vision-full-source',assetId='vision-source',inFrame=0,outFrame=3,label='完整源视频')])
        self.assertEqual(p['visionReview']['events'][0]['frame'],1)
        self.assertEqual(p['review']['rows'],[]);self.assertEqual(p['answers'],{});self.assertEqual(p['approval'],{})
        self.assertFalse(context(p)['visionReview']['adoptedForStatistics'])
        with self.assertRaisesRegex(ValueError,'already exists'):self.plan()

    def test_uncommitted_corrupt_and_cross_source_inputs_fail_closed(self):
        self.proposal['events'][0]['seconds']='3/20';write(self.root/'proposals.json',self.proposal)
        with self.assertRaisesRegex(ValueError,'committed source PTS'):self.plan()
        self.proposal['events'][0]['seconds']='71/500';self.proposal['sourceIdentity']['sha256']='0'*64;write(self.root/'proposals.json',self.proposal)
        with self.assertRaisesRegex(ValueError,'different sources'):self.plan()
        self.proposal['sourceIdentity']=identity(self.source);write(self.root/'proposals.json',self.proposal)
        (self.stream.parent/'chunks/test.jsonl').write_text('{}\n')
        with self.assertRaisesRegex(ValueError,'chunk changed'):self.plan()

    def test_annotation_roundtrip_undo_conflict_and_approval_separation(self):
        p=self.project();directory=self.root/'edit';directory.mkdir();write(directory/'project.json',p);store=Store(directory)
        op=dict(type='vision-review',eventId='E1',annotation=dict(verdict='confirmed',kind='bounce',side='far',frame=2,note='Synthetic reviewed correction',evidence=['synthetic://native-frame-176'],reviewSeconds=2.5))
        saved=store.apply(0,op);self.assertEqual(saved['visionAnnotations']['E1']['kind'],'bounce')
        self.assertEqual(saved['answers'],{});self.assertEqual(saved['needsRebuild'],[]);self.assertEqual(saved['approval'],{})
        self.assertEqual(Store(directory).get()['visionAnnotations'],saved['visionAnnotations'])
        with self.assertRaises(Conflict):store.apply(0,op)
        undone=store.apply(1,dict(type='undo'));self.assertEqual(undone['visionAnnotations'],{})
        redone=store.apply(2,dict(type='redo'));self.assertEqual(redone['visionAnnotations']['E1']['frame'],2)
        with self.assertRaisesRegex(ValueError,'match approval'):store.apply(3,dict(type='approval',field='pointAttribution',confirmed=True))

    def test_annotation_and_proposal_cannot_silently_change_authority_or_clock(self):
        p=self.project()
        for changed in [dict(verdict='confirmed',kind='racket_contact',frame=3),dict(verdict='confirmed',frame=1),dict(verdict='pending',winner='A'),dict(reviewSeconds=float('nan')),dict(kind=[]),dict(side={})]:
            q=copy.deepcopy(p);q['visionAnnotations']={'E1':changed}
            with self.assertRaises(ValueError):validate(q)
        q=copy.deepcopy(p);q['visionReview']['events'][0]['adjudication']='adopted'
        with self.assertRaisesRegex(ValueError,'unadopted'):validate(q)
        q=copy.deepcopy(p);q['visionReview']['events'][0]['frame']=2
        q['visionReview']['events'][0]['seconds']='1/10'
        with self.assertRaisesRegex(ValueError,'disagree'):validate(q)


if __name__ == '__main__':unittest.main()
