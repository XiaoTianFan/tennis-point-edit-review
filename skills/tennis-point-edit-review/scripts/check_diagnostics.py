import copy,unittest
from diagnostic_stats import aggregate_diagnostics

def point(pid,server,winner,n,end):return dict(pointId=pid,server=server,winner=winner,shots=n,ending=end,statsIncluded=True)
def events(p,hand='FH',direction='net'):
 return [dict(pointId=p['pointId'],shotIndex=i,hitter=p['server'] if i%2 else ('B' if p['server']=='A' else 'A'),countsAsShot=True,hand=hand if i==p['shots'] else None,errorDirection=direction,evidence={'sheet':'synthetic-fixture'}) for i in range(1,p['shots']+1)]
class Checks(unittest.TestCase):
 def test_double_fault_not_in_rally_denominator(self):
  a=point('p1','A','B',0,'DF');b=point('p2','A','A',1,'ACE');d=aggregate_diagnostics([a,b],events(b))
  self.assertEqual(d['rallyPoints'],1);self.assertEqual(d['zeroShotDoubleFaults'],1);self.assertEqual(d['metrics']['A']['shortWinRate']['percent'],100)
 def test_serve_plus_one_excludes_return_error(self):
  a=point('p1','A','A',2,'UE');b=point('p2','A','B',3,'UE');d=aggregate_diagnostics([a,b],events(a)+events(b))
  self.assertEqual(d['metrics']['A']['servePlusOneWon']['denominator'],1);self.assertEqual(d['metrics']['A']['servePlusOneErrors'],1)
 def test_unknown_hand_keeps_terminal_total(self):
  p=point('p1','B','B',2,'FE');d=aggregate_diagnostics([p],events(p,None,'out'))
  self.assertEqual(d['metrics']['A']['terminalHands']['FE']['unknown'],1);self.assertEqual(d['metrics']['A']['errorOut']['percent'],100)
 def test_dead_ball_swing_does_not_count(self):
  p=point('p1','A','A',3,'W');rr=events(p);rr.append(dict(pointId='p1',countsAsShot=False,shotIndex=4,hitter='B',reason='missed swing'))
  self.assertEqual(aggregate_diagnostics([p],rr)['shotCount'],3)
 def test_duplicate_missing_contact_and_wrong_hitter_fail(self):
  p=point('p1','A','B',3,'UE');rr=events(p)
  for ss in (rr+rr[:1],rr[1:],copy.deepcopy(rr)):
   if len(ss)==3:ss[1]['hitter']='A'
   with self.assertRaises(ValueError):aggregate_diagnostics([p],ss)
 def test_rally_frequency_differs_from_win_rate(self):
  pp=[point('p1','A','A',3,'W'),point('p2','A','B',3,'UE'),point('p3','B','B',9,'W')]
  d=aggregate_diagnostics(pp,sum((events(p) for p in pp),[]))
  self.assertEqual(d['rallyDistribution']['short']['percent'],66.7);self.assertEqual(d['metrics']['A']['shortWinRate']['percent'],50)
 def test_empty_scope_not_zero_percent(self):
  d=aggregate_diagnostics([],[]);self.assertIsNone(d['metrics']['A']['servePlusOneWon']['percent'])
if __name__=='__main__':unittest.main()


