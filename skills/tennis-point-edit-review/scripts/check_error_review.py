import copy,unittest,json
from check_diagnostics import point,events
from diagnostic_stats import aggregate_diagnostics
from error_review import review_coverage,validate_error_assessment
from template_pack import build_stats_pages,ROOT

def error(pid,classification,motion):
 p=point(pid,'B','B',2,'OTHER' if classification=='unknown' else classification)
 p.update(terminalError=True,errorAssessment=dict(reviewed=True,classification=classification,
   opponentPressure={'UE':'not_evidenced','FE':'imposed','unknown':'unclear'}[classification],
   basis='incoming_ball_and_available_response',reason='Synthetic incoming-shot evidence',
   evidence={'sourceTimes':[1,2,3]}))
 ss=events(p);ss[-1].update(terminalErrorMotion=motion,motionEvidence={'sourceTimes':[2.8,3,3.2]})
 return p,ss

class Checks(unittest.TestCase):
 def test_moving_ue_and_stationary_fe_are_independent(self):
  a,sa=error('a','UE','moving');b,sb=error('b','FE','stationary')
  self.assertEqual(review_coverage([a,b])['reviewedErrors'],2)
  m=aggregate_diagnostics([a,b],sa+sb)['metrics']['A']
  self.assertEqual(m['ueMotionCounts'],dict(moving=1,stationary=0,unknown=0))
  self.assertEqual(m['errorMotionCounts'],dict(moving=1,stationary=1,unknown=0))
 def test_unknown_pressure_not_forced_into_ue_but_keeps_error_direction(self):
  a,sa=error('a','UE','stationary');b,sb=error('b','unknown','moving')
  m=aggregate_diagnostics([a,b],sa+sb)['metrics']['A']
  self.assertEqual(m['ueMoving'],0);self.assertEqual(m['ueStationary'],1)
  self.assertEqual(m['unclassifiedErrors'],1);self.assertEqual(m['errorNet']['denominator'],2)
 def test_unknown_ue_motion_is_not_stationary(self):
  a,sa=error('a','UE','unknown');m=aggregate_diagnostics([a],sa)['metrics']['A']
  self.assertEqual(m['ueMoving']+m['ueStationary'],0);self.assertEqual(m['ueMotionCounts']['unknown'],1)
 def test_pressure_contradiction_or_missing_observation_rejected(self):
  p,_=error('e','FE','moving')
  for field,val in [('opponentPressure','not_evidenced'),('basis','motion_only'),('evidence',None),('reviewed',False)]:
   q=copy.deepcopy(p);q['errorAssessment'][field]=val
   with self.assertRaises(ValueError):validate_error_assessment(q)
 def test_unreviewed_errors_fail_coverage(self):
  with self.assertRaises((KeyError,ValueError)):review_coverage([point('a','B','B',2,'UE')])
 def test_unknown_pressure_does_not_remove_actual_third_error(self):
  p=point('e','A','B',3,'OTHER');p['terminalError']=True
  m=aggregate_diagnostics([p],events(p))['metrics']['A']
  self.assertEqual(m['servePlusOneErrors'],1);self.assertEqual(m['unclassifiedErrors'],1)
 def panels(self,ue_a=4,ue_b=5,unclassified_a=1):
  keys=[r['key'] for p in json.loads((ROOT/'examples/stats-pages.json').read_text(encoding='utf8')) for r in p['rows']]
  m={x:{k:0 for k in keys} for x in 'AB'}
  for x in 'AB':m[x]['terminalHands']={k:dict(FH=0,BH=0,other=0,unknown=0) for k in ('W','UE','FE')}
  m['A'].update(UE=ue_a,FE=6,unclassifiedErrors=unclassified_a,ueMoving=1,ueStationary=3)
  m['B'].update(UE=ue_b,FE=2,unclassifiedErrors=0,ueMoving=2,ueStationary=3)
  speed={x:{k:60 for k in ('fastestServeKphEstimate','firstServeMeanKphEstimate','secondServeMeanKphEstimate')} for x in 'AB'}
  d={'rallyDistribution':{k:dict(numerator=0,denominator=0) for k in ('short','medium','long')}}
  return build_stats_pages(m,speed,d)
 def test_ue_compares_adopted_count_with_unknown_separate(self):
  rows={r['key']:r for r in self.panels()[3]['rows']}
  self.assertEqual(rows['UE']['highlight'],'A');self.assertEqual(rows['FE']['highlight'],'B')
 def test_ue_ties_stay_neutral_even_with_unknown(self):
  rows={r['key']:r for r in self.panels(4,4,8)[3]['rows']}
  self.assertIsNone(rows['UE']['highlight'])
 def test_fewer_ue_can_be_either_player(self):
  rows={r['key']:r for r in self.panels(9,4,20)[3]['rows']}
  self.assertEqual(rows['UE']['highlight'],'B')
 def test_default_motion_metrics_are_ue_counts_and_neutral(self):
  rows=self.panels()[4]['rows'][:2]
  self.assertEqual([r['key'] for r in rows],['ueMoving','ueStationary'])
  self.assertEqual([r['a'] for r in rows],['1','3'])
  self.assertTrue(all(r['highlight'] is None for r in rows))

if __name__=='__main__':unittest.main()
