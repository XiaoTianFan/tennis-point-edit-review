"""Initial labeling is usable with no agent decisions and cannot reset drafts."""
import copy
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/tennis-point-edit-review/scripts'))

from local_model import Store, read, write, review_payload
from local_media import prepare_media
from prepare_review import prepare, publish
from review_io import build, merge


def sample():
    return dict(title='Synthetic initial labeling', outputLanguage='en', fps='25',
        width=160, height=90, players=[dict(id='A',name='Player A'),dict(id='B',name='Player B')],
        assets=[dict(id='src',path='synthetic.mp4',fps='25',frames=100,timing='cfr-proxy')],
        clips=[dict(id='c1',assetId='src',inFrame=0,outFrame=30,pointId='P001'),
               dict(id='c2',assetId='src',inFrame=30,outFrame=50,pointId='P001'),
               dict(id='c3',assetId='src',inFrame=50,outFrame=100,pointId='P002')],
        review=dict(source='synthetic',ledgerRevision='synthetic-v1',rows=[]),overlays=[])


class InitialReviewTests(unittest.TestCase):
    def test_grouped_points_and_unknowns_without_invented_outcomes(self):
        plan, review, ledger = prepare(sample(), '.', mode='human-first')
        self.assertEqual(plan['workingMode'],'human-first')
        self.assertEqual(len(review['rows']),2)
        self.assertEqual(len(review['rows'][0]['evidenceRanges']),2)
        self.assertEqual(review['rows'][1]['mainStartSeconds'],2)
        self.assertTrue(all(r['initial']=={} and r['serverId'] is None for r in review['rows']))
        self.assertEqual(ledger['ledgerRevision'],'synthetic-v1:initial')
        self.assertTrue(all(p['reviewStatus']=='pending' for p in ledger['points']))
        self.assertNotIn('winner', ledger['points'][0])

    def test_unverified_seam_grouping_is_explicit_and_published_review_is_not_reset(self):
        p = sample(); p['clips'][0].pop('pointId')
        with self.assertRaises(ValueError): prepare(p,'.')
        _, review, _ = prepare(p,'.',provisional=True)
        self.assertTrue(review['rows'][0]['candidatePoint'])
        self.assertNotEqual(review['rows'][0]['pointId'],'P001')
        p['review']['rows']=[dict(pointId='P001')]
        with self.assertRaises(ValueError): prepare(p,'.')

    def test_unknown_server_allowed_only_for_initial_labeling(self):
        with tempfile.TemporaryDirectory() as work:
            _, review, _ = prepare(sample(),'.')
            build(review,Path(work)/'initial.html')
            review.pop('purpose')
            with self.assertRaises(ValueError): build(review,Path(work)/'ordinary.html')

    def test_merge_preserves_pending_and_guards_metadata(self):
        _, review, ledger = prepare(sample(),'.')
        payload = dict(schema='tennis-point-review/v1',purpose='initial-labeling',source=ledger['source'],
                       ledgerRevision=ledger['ledgerRevision'], rows=[dict(pointId='P001',status='pending')])
        self.assertNotIn('winner',merge(ledger,payload)['points'][0])
        row = dict(pointId='P001',status='resolved',serverId='B',serveNumber=2,gameNumber=1,setNumber=1,
                   scoringPlayerId='A',deadBallType='net',doubleFaultConfirmed=True,reviewConfirmed=True)
        payload['rows']=[row]
        result = merge(ledger,payload)
        self.assertEqual(result['points'][0]['serverId'],'B')
        self.assertEqual(result['points'][0]['winner'],'A')
        self.assertEqual(result['points'][0]['serveNumber'],2)
        self.assertNotIn('winner',ledger['points'][0])
        for update in (dict(serverId=None),dict(serverId='A'),dict(serveNumber=3),dict(gameNumber=1.5)):
            with self.assertRaises(ValueError): merge(ledger,{**payload,'rows':[{**row,**update}]})
        with self.assertRaises(ValueError): merge({**ledger,'purpose':None},payload)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
    def test_both_surfaces_resume_and_revision_protect_human_labels(self):
        with tempfile.TemporaryDirectory() as work:
            work=Path(work)
            source=work/'synthetic.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=green:s=160x90:r=25:d=4',
                            '-c:v','libx264',str(source)],check=True)
            prepare_media(source,work/'proxy.mp4')
            p=sample();p['assets']=[dict(id='src',metadata='proxy.media.json')]
            write(work/'plan.json',p)
            publish(work/'plan.json',work/'initial',mode='human-first')
            self.assertFalse(read(work/'initial/handoff.json')['adjudicationPerformed'])
            self.assertEqual(read(work/'initial/handoff.json')['nextAction'],'wait-for-human-labeling')
            store=Store(work/'initial/edit')
            self.assertEqual([r['status'] for r in review_payload(store.get())['rows']],['pending','pending'])
            # No server means no inferred double-fault winner.
            with self.assertRaises(ValueError):
                store.apply(0,dict(type='review',pointId='P001',answer=dict(doubleFaultConfirmed=True)))
            answer=dict(serverId='B',scoringPlayerId='A',deadBallType='net',reviewConfirmed=True,serveNumber=2)
            store.apply(0,dict(type='review',pointId='P001',answer=answer))
            payload=review_payload(Store(work/'initial/edit').get())
            self.assertEqual(payload['rows'][0]['serverId'],'B')
            self.assertEqual(payload['rows'][0]['status'],'resolved')
            self.assertTrue(merge(read(work/'initial/ledger.json'),payload)['points'][0]['userReviewConfirmed'])
            with self.assertRaises(ValueError): publish(work/'plan.json',work/'initial')
            self.assertEqual(store.get()['answers']['P001']['serverId'],'B')


if __name__ == '__main__':
    unittest.main()
