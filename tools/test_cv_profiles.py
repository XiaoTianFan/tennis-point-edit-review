"""Motion labels, provenance, persistence and calibration/query leakage contracts."""
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/tennis-point-edit-review/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cv_profiles as profiles
import test_cv_review as event_review
from local_model import Store, context, validate, write


class MotionExamples(event_review.EventReviewContract):
    def setUp(self):
        super().setUp()
        self.proposal['events'][0]['motionExample'] = dict(profileId='synthetic-session',recordingGroupIds=['recording-A'],intervalSeconds=['1/10','1/5'],suggested=dict(family='forehand',form='volley'))
        write(self.root/'proposals.json', self.proposal)

    def decision(self):
        return dict(status='agent_observed',labels=dict(playerId='A',handedness='left',family='forehand',form='volley',spin='unknown'),actor=dict(role='agent',id='synthetic-agent'))

    def test_example_roundtrip_profile_revision_and_undo(self):
        p=self.project();directory=self.root/'motion-edit';directory.mkdir();write(directory/'project.json',p);store=Store(directory)
        decision=self.decision();op=dict(type='vision-review',eventId='E1',annotation=dict(motionExample=decision))
        saved=store.apply(0,op);profile=context(saved)['visionReview']['motionProfile']
        self.assertEqual(profile['revision'],1);self.assertEqual(profile['examples'][0]['decision']['labels']['handedness'],'left')
        self.assertFalse(profile['adoptedForTraining']);self.assertEqual(saved['answers'],{});self.assertEqual(saved['needsRebuild'],[])
        decision.update(status='owner_confirmed',actor=dict(role='owner',id='synthetic-owner'));store.apply(1,op)
        self.assertEqual(Store(directory).get()['visionAnnotations']['E1']['motionExample']['status'],'owner_confirmed')
        undone=store.apply(2,dict(type='undo'));self.assertEqual(undone['visionAnnotations']['E1']['motionExample']['status'],'agent_observed')
        redone=store.apply(3,dict(type='redo'));self.assertEqual(context(redone)['visionReview']['motionProfile']['revision'],4)
        self.assertTrue((directory/'history/000001.json').exists())

    def test_invalid_motion_labels_provenance_and_bounds(self):
        p=self.project()
        changes=[dict(status='owner_confirmed'),dict(labels=dict(playerId='missing')),dict(labels=dict(family='serve',form='volley')),dict(labels=dict(family='backhand',spin='kick')),dict(actor=dict(role='agent',id=''))]
        for change in changes:
            q=copy.deepcopy(p);q['visionAnnotations']={'E1':dict(motionExample={**self.decision(),**change})}
            with self.assertRaises(ValueError):validate(q)
        q=copy.deepcopy(p);q['visionReview']['events'][0]['motionExample']['intervalSeconds']=['0','1/5']
        with self.assertRaisesRegex(ValueError,'outside source'):validate(q)
        q=copy.deepcopy(p);del q['visionReview']['events'][0]['motionExample'];q['visionAnnotations']={'E1':dict(motionExample=self.decision())}
        with self.assertRaisesRegex(ValueError,'bound example'):validate(q)

    def test_skip_and_unknown_do_not_fill_stroke_or_hand(self):
        for state in ('unknown','skipped'):
            result=profiles.annotation(dict(status=state,labels={},actor=dict(role='owner',id='synthetic-owner')),{'A','B'})
            self.assertEqual(result['labels']['handedness'],'unknown');self.assertIsNone(result['labels']['playerId'])

    def test_changed_example_clears_decision_and_undo_restores_both(self):
        p=self.project();directory=self.root/'attach-edit';directory.mkdir();write(directory/'project.json',p);store=Store(directory)
        store.apply(0,dict(type='vision-review',eventId='E1',annotation=dict(motionExample=self.decision())))
        changed=copy.deepcopy(self.proposal['events'][0]['motionExample']);changed['profileId']='another-profile'
        saved=store.apply(1,dict(type='motion-example',eventId='E1',proposal=changed))
        self.assertNotIn('motionExample',saved['visionAnnotations']['E1'])
        undone=store.apply(2,dict(type='undo'))
        self.assertEqual(undone['visionReview']['events'][0]['motionExample']['profileId'],'synthetic-session')
        self.assertEqual(undone['visionAnnotations']['E1']['motionExample']['status'],'agent_observed')


class CalibrationIsolation(unittest.TestCase):
    def test_same_recording_alternate_export_and_context_excluded(self):
        profile=dict(schema=profiles.SCHEMA,revision=3,examples=[dict(recordingGroupIds=['A'],sourceIdentity=dict(sha256='a'*64),intervalSeconds=['10','15'])])
        def query(i,a,b,digest='a',group='A'):
            return dict(id=i,sourceIdentity=dict(sha256=digest*64),recordingGroupIds=[group],intervalSeconds=[str(a),str(b)])
        queries=[query('inside',12,13),query('context',16,17),query('clear',20,22),query('alternate',40,42,digest='b'),query('new',10,15,digest='c',group='C')]
        split=profiles.split_windows(profile,queries,mode='session_assisted',context_seconds=1)
        self.assertEqual([q['id'] for q in split['eligible']],['clear','new'])
        self.assertEqual(len(split['excluded']),3)
        unseen=profiles.split_windows(profile,queries,mode='unseen_recording',context_seconds=1)
        self.assertEqual([q['id'] for q in unseen['eligible']],['new'])
        with self.assertRaisesRegex(ValueError,'contradictory'):
            profiles.split_windows(profile,[query('mislabeled',40,42,group='C')],mode='session_assisted',context_seconds=1)
        with self.assertRaises(ValueError):profiles.split_windows(profile,queries,mode='session_assisted',context_seconds=float('nan'))


if __name__=='__main__':unittest.main()
