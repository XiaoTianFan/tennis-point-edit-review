"""Regression checks for incomplete-game awards, coverage, lineage and templates."""
import copy,json,unittest
from pathlib import Path
from score_audit import audit
from stats_aggregate import aggregate
from evidence_audit import audit_coverage,audit_lineage
from speed_quality import audit_speed_quality
from template_pack import bundle,build_stats_pages
from package_check import check,ROOT
from review_io import merge

def rows(seq):return [dict(pointId=f'P{i+1:03}',winner=w) for i,w in enumerate(seq)]
def cfg():return dict(mode='timed',advantage=False,nextServer='B')
def award():return dict(recordedGameWinner='B',exceptionType='onsite_award_before_rule_completion',exceptionConfirmed=True,exceptionNote='Explicitly adopted onsite award; incomplete game')
class Checks(unittest.TestCase):
    def test_incomplete_award_keeps_points_and_changes_server(self):
        rr=rows('ABABB'+'A');rr[4].update(award());rr[5]['server']='A'
        a=audit(cfg(),rr)
        self.assertEqual(a['conflicts'],[]);self.assertEqual(a['games'][0]['rawPoints'],{'A':2,'B':3})
        self.assertIsNone(a['games'][0]['rulesWinner']);self.assertFalse(a['games'][0]['rulesComplete'])
        self.assertEqual(a['rulesCompleteGameCount'],0);self.assertEqual(a['score']['games'],{'A':0,'B':1})
        self.assertEqual(a['states'][5]['server'],'A');self.assertEqual(a['states'][5]['before']['points'],{'A':0,'B':0})
        self.assertEqual(len(a['states']),6)
    def test_early_award_without_confirmation_is_conflict(self):
        for changed in [{'exceptionConfirmed':False},{'exceptionNote':''},{'exceptionType':'guess'}]:
            rr=rows('ABABB');rr[-1].update(award(),**{});rr[-1].update(changed)
            a=audit(cfg(),rr);self.assertTrue(a['conflicts']);self.assertEqual(a['games'],[])
    def test_early_award_cannot_close_tiebreak(self):
        rr=rows('ABABB');rr[-1].update(award())
        a=audit({'mode':'tiebreak','nextServer':'A'},rr);self.assertTrue(a['conflicts']);self.assertFalse(a['matchComplete'])
    def test_award_does_not_create_points_or_breaks_in_stats(self):
        rr=rows('ABABB');rr[-1].update(award())
        for r in rr:r.update(server='B',serveNumber=1,ending='UE',shots=2,positionsAfterServe=[{'player':'A','zone':'near'}],netPlayers=[],statsIncluded=True)
        a=audit(cfg(),rr);s=aggregate({'scope':'synthetic','audit':a,'points':rr})
        self.assertEqual(s['pointCount'],5);self.assertEqual(s['metrics']['B']['held']['numerator'],1)
        self.assertEqual(s['metrics']['A']['pointsWon'],2);self.assertEqual(s['metrics']['A']['breakConverted']['denominator'],0)
    def test_unfinished_tail_without_award_stays_unfinished(self):
        a=audit(cfg(),rows('ABABB'));self.assertEqual(a['games'],[]);self.assertEqual(a['score']['points'],{'A':2,'B':3})
    def test_complete_coverage(self):
        d=json.loads((ROOT/'examples/coverage-data.json').read_text(encoding='utf8'))
        self.assertTrue(audit_coverage(d)['complete'])
    def test_coverage_gap_and_overlap(self):
        d=json.loads((ROOT/'examples/coverage-data.json').read_text(encoding='utf8'))
        d['intervals'][1]['startUs']+=1;self.assertEqual(audit_coverage(d)['findings'][0]['issue'],'uncovered_gap')
        d['intervals'][1]['startUs']-=2;self.assertEqual(audit_coverage(d)['findings'][0]['issue'],'overlapping_intervals')
    def test_unreviewed_and_source_gap_not_passed(self):
        d=json.loads((ROOT/'examples/coverage-data.json').read_text(encoding='utf8'))
        d['intervals'][1]['kind']='source_gap';self.assertFalse(audit_coverage(d)['complete'])
    def test_no_silent_deletion(self):
        d=json.loads((ROOT/'examples/coverage-data.json').read_text(encoding='utf8'));d['intervals'][0].pop('reason')
        with self.assertRaises(ValueError):audit_coverage(d)
    def test_source_order_not_point_number(self):
        pp=[dict(pointId='P002',sourceOrder=0,sourceStartUs=10),dict(pointId='P008',sourceOrder=0,sourceStartUs=1)]
        self.assertEqual(audit_lineage(pp)['activePointIdsInSourceOrder'],['P008','P002'])
    def test_retired_merged_candidate_cannot_count(self):
        pp=[dict(pointId='P001',sourceOrder=0,sourceStartUs=1),dict(pointId='P002',active=False)]
        link=[dict(kind='merge',**{'from':['P001','P002'],'to':['P001']},reason='Same physical point',revision='v2')]
        self.assertEqual(audit_lineage(pp,link)['activePointIdsInSourceOrder'],['P001'])
        pp[1].update(active=True,sourceOrder=0,sourceStartUs=2)
        with self.assertRaises(ValueError):audit_lineage(pp,link)
    def test_split_preserves_history(self):
        pp=[dict(pointId='P001',active=False),dict(pointId='P002',sourceOrder=0,sourceStartUs=1),dict(pointId='P003',sourceOrder=0,sourceStartUs=2)]
        link=[dict(kind='split',**{'from':['P001'],'to':['P002','P003']},reason='Two distinct points',revision='v2')]
        self.assertEqual(len(audit_lineage(pp,link)['activePointIdsInSourceOrder']),2)
    def test_speed_imputation_shift_and_peak_flag(self):
        rr=[dict(setNumber=1,serverId='A',serveNumber=1,serveId='S1',launchSpeedKphEstimate=100,method='endpoint_drag_model'),dict(setNumber=1,serverId='A',serveNumber=1,serveId='S2',launchSpeedKphEstimate=80,method='model_imputed',imputationBasis='same group')]
        q=audit_speed_quality(rr);self.assertEqual(q['groups'][0]['imputationMeanShiftKph'],-10)
        self.assertEqual(q['agentChecks'][0]['issue'],'agent_must_reinspect_fastest_candidate');self.assertFalse(q['requiresUserForm'])
    def test_speed_boundary_flag_even_after_peak_check(self):
        q=audit_speed_quality([dict(setNumber=1,serverId='A',serveNumber=1,serveId='S1',launchSpeedKphEstimate=100,method='projected_flight_model',fitAtParameterBoundary=True,fastestCandidateReviewed=True)])
        self.assertEqual(q['agentChecks'][0]['issue'],'recheck_model_before_publication')
    def test_template_bundle_long_note_grows(self):
        b=bundle('explanation',{'detail':'这是用于检验长说明边界的文字。'*7})
        self.assertGreater(b['naturalSize']['height'],132)
        self.assertEqual(b['placement1080p']['height'],b['naturalSize']['height']*.8)
    def test_seven_components_and_five_pages(self):
        self.assertEqual(check()['componentCount'],7)
        for c in ['scoreboard','serveLabel','explanation','statsPanel','reviewLabel','reviewId','serveSpeed']:self.assertTrue(bundle(c)['code'])
    def test_stats_uses_launch_not_legacy(self):
        specs=json.loads((ROOT/'examples/stats-pages.json').read_text(encoding='utf8'))
        metrics={p:{r['key']:0 for page in specs for r in page['rows']} for p in 'AB'}
        for p in 'AB':
            metrics[p].update(firstServeMeanKph=999,secondServeIn={'numerator':3,'denominator':4},terminalHands={k:dict(FH=1,BH=2,other=0,unknown=1) for k in ('W','UE','FE')})
        speed={p:dict(fastestServeKphEstimate=110,allServeMeanKphEstimate=90,firstServeMeanKphEstimate=100,secondServeMeanKphEstimate=80) for p in 'AB'}
        diag={'rallyDistribution':{k:dict(numerator=1,denominator=3) for k in ('short','medium','long')}}
        pages=build_stats_pages(metrics,speed,diag)
        self.assertEqual(pages[1]['rows'][3]['a'],'75%  (3/4)');self.assertEqual(pages[1]['rows'][8]['a'],'约 110 km/h');self.assertEqual(pages[1]['rows'][9]['a'],'约 100 km/h')
        self.assertIn('未判 1',pages[3]['rows'][3]['asub'])
        self.assertIn('33.3%',pages[3]['rows'][0]['sub'])
    def test_explicit_result_updates_existing_winner_internally(self):
        d={'source':'example','ledgerRevision':'v1','players':[{'id':'A'},{'id':'B'}],'points':[{'pointId':'P001','winner':'A','adoptedWinner':'A'}]}
        r={'schema':'tennis-point-review/v1','source':'example','ledgerRevision':'v1','rows':[{'pointId':'P001','status':'resolved','reviewConfirmed':True,'scoringPlayerId':'B'}]}
        out=merge(d,r);self.assertEqual(out['points'][0]['winner'],'B');self.assertFalse(out['requiresUserFieldByFieldReview']);self.assertEqual(d['points'][0]['winner'],'A')
if __name__=='__main__':unittest.main()


