"""Forward-review state, source gaps, evidence and persistence boundaries."""
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/tennis-point-edit-review/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_cv_review as event_review
from local_model import Store, context, validate, write
import cv_terminal


class TerminalReview(unittest.TestCase):
    plan = event_review.EventReviewContract.plan
    project = event_review.EventReviewContract.project

    def setUp(self):
        event_review.EventReviewContract.setUp(self)
        self.proposal['events'][0].update(kind='dead_ball', intervalSeconds=['1/10', '19/100'],
            terminalWindow=dict(schema=cv_terminal.SCHEMA, anchor=dict(kind='manual', seconds='9/50')))
        write(self.root/'proposals.json', self.proposal)

    def decision(self, status='verified'):
        return dict(verdict=cv_terminal.VERDICTS[status], kind='dead_ball', frame=1, note='Synthetic forward observation',
            terminalReview=dict(status=status, lastLiveSeconds='11/100', firstDeadBallWindowSeconds=['7/50', '3/20'],
                observedThroughSeconds='22/125', continuationFound=False, cessationObserved=True, sourceGapSeconds=None,
                sampling='sampled_native', nativeEvidence=['synthetic://native-pts-sequence'], actor=dict(role='agent', id='synthetic-reviewer')))

    def test_roundtrip_undo_and_boundaries_remain_unadopted(self):
        p=self.project(); directory=self.root/'terminal-edit';directory.mkdir();write(directory/'project.json',p);store=Store(directory)
        saved=store.apply(0,dict(type='vision-review',eventId='E1',annotation=self.decision()))
        self.assertEqual(Store(directory).get()['visionAnnotations'],saved['visionAnnotations'])
        review=context(saved)['visionReview'];self.assertEqual(review['terminalStatusCounts']['verified'],1)
        self.assertFalse(review['adoptedForBoundaries']);self.assertFalse(review['adoptedForStatistics'])
        self.assertEqual(saved['answers'],{});self.assertEqual(saved['approval'],{});self.assertEqual(saved['clips'],p['clips'])
        self.assertEqual(store.apply(1,dict(type='undo'))['visionAnnotations'],{})
        self.assertEqual(store.apply(2,dict(type='redo'))['visionAnnotations']['E1']['terminalReview']['status'],'verified')

    def test_precision_requires_native_bracket_forward_extent_and_consistency(self):
        p=self.project()
        changes=[dict(firstDeadBallWindowSeconds=None),dict(firstDeadBallWindowSeconds=['1/10','3/20']),
                 dict(observedThroughSeconds='3/20'),dict(nativeEvidence=[]),dict(sampling='continuous_playback'),
                 dict(sourceGapSeconds='29/200'),dict(continuationFound=True),dict(cessationObserved=False),
                 dict(lastLiveSeconds=True),dict(actor=None),dict(firstDeadBallWindowSeconds=['nan','3/20'])]
        for change in changes:
            with self.subTest(change=change):
                q=copy.deepcopy(p);a=self.decision();a['terminalReview'].update(change);q['visionAnnotations']={'E1':a}
                with self.assertRaises(ValueError):validate(q)
        for parent in [dict(verdict='uncertain'),dict(kind='bounce'),dict(frame=0,note='')]:
            q=copy.deepcopy(p);q['visionAnnotations']={'E1':{**self.decision(),**parent}}
            with self.assertRaises(ValueError):validate(q)

    def test_cessation_does_not_manufacture_a_death_or_bridge_a_gap(self):
        p=self.project();a=self.decision('cessation_only');a['terminalReview'].update(firstDeadBallWindowSeconds=None,nativeEvidence=[],sampling='navigation')
        p['visionAnnotations']={'E1':a};validate(p)
        self.assertIsNone(context(p)['visionReview']['annotations']['E1']['terminalReview']['firstDeadBallWindowSeconds'])
        for change in [dict(firstDeadBallWindowSeconds=['7/50','3/20']),dict(sourceGapSeconds='3/20')]:
            q=copy.deepcopy(p);q['visionAnnotations']['E1']['terminalReview'].update(change)
            with self.assertRaises(ValueError):validate(q)

    def test_continuation_truncation_and_graphics_are_distinct(self):
        p=self.project()
        variants=[('continuation',dict(firstDeadBallWindowSeconds=None,continuationFound=True,cessationObserved=False)),
                  ('source_truncated',dict(firstDeadBallWindowSeconds=None,sourceGapSeconds='17/100',continuationFound=None,cessationObserved=None)),
                  ('not_play',dict(lastLiveSeconds=None,firstDeadBallWindowSeconds=None,continuationFound=None,cessationObserved=None))]
        for state,change in variants:
            with self.subTest(state=state):
                a=self.decision(state);a['terminalReview'].update(change);q=copy.deepcopy(p);q['visionAnnotations']={'E1':a};validate(q)
                q['visionAnnotations']['E1']['terminalReview']['cessationObserved']=True
                with self.assertRaises(ValueError):validate(q)
        a=self.decision('continuation');a['terminalReview'].update(firstDeadBallWindowSeconds=None,continuationFound=True,cessationObserved=False,sourceGapSeconds='3/20')
        p['visionAnnotations']={'E1':a}
        with self.assertRaisesRegex(ValueError,'source gap'):validate(p)
        a['terminalReview']['lastLiveSeconds']='17/100'
        with self.assertRaisesRegex(ValueError,'source gap'):validate(p)

    def test_observation_cannot_escape_or_attach_to_another_event(self):
        p=self.project();p['visionAnnotations']={'E1':self.decision()}
        changes=[dict(observedThroughSeconds='1/4'),dict(sourceGapSeconds='19/100')]
        for change in changes:
            q=copy.deepcopy(p);q['visionAnnotations']['E1']['terminalReview'].update(change)
            with self.assertRaises(ValueError):validate(q)
        q=copy.deepcopy(p);del q['visionReview']['events'][0]['terminalWindow']
        with self.assertRaisesRegex(ValueError,'bound terminal'):validate(q)
        q=copy.deepcopy(p);del q['visionAnnotations']['E1']['terminalReview']
        with self.assertRaisesRegex(ValueError,'forward observation'):validate(q)

    def test_recording_end_anchor_cannot_be_an_interior_timestamp(self):
        p=self.project();anchor=p['visionReview']['events'][0]['terminalWindow']['anchor'];anchor['kind']='recording_end'
        with self.assertRaisesRegex(ValueError,'source coverage'):validate(p)
        anchor['seconds']='22/125';validate(p)
        del p['visionReview']['sourceCoverage']
        with self.assertRaisesRegex(ValueError,'source coverage'):validate(p)


if __name__ == '__main__':unittest.main()
