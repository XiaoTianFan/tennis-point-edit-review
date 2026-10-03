import unittest
from check_diagnostics import point,events
from diagnostic_stats import aggregate_diagnostics

class Checks(unittest.TestCase):
 def error(self,pid,ending,motion):
  p=point(pid,'B','B',2,ending);ss=events(p)
  ss[-1].update(terminalErrorMotion=motion,motionEvidence={'sourceTimes':[1,1.1,1.2]})
  return p,ss
 def test_only_losing_terminal_errors_including_return(self):
  a,sa=self.error('e1','UE','moving');b,sb=self.error('e2','FE','stationary')
  w=point('w','A','A',3,'W');sw=events(w);sw[-1]['terminalErrorMotion']='moving'
  ace=point('ace','B','B',1,'ACE');df=point('df','B','A',0,'DF')
  d=aggregate_diagnostics([a,b,w,ace,df],sa+sb+sw+events(ace))
  self.assertEqual(d['metrics']['A']['errorMotionCounts'],dict(moving=1,stationary=1,unknown=0))
  self.assertEqual(d['metrics']['A']['errorMoving']['denominator'],2)
  self.assertEqual(d['metrics']['B']['errorMoving']['denominator'],0)
 def test_unknown_retains_denominator(self):
  a,sa=self.error('e1','UE','moving');b,sb=self.error('e2','FE',None)
  m=aggregate_diagnostics([a,b],sa+sb)['metrics']['A']
  self.assertEqual(m['errorMoving']['percent'],50);self.assertEqual(m['errorStationary']['percent'],0)
  self.assertEqual(m['errorMotionCounts']['unknown'],1)
 def test_no_per_shot_motion_counting(self):
  p=point('e','A','B',3,'UE');ss=events(p)
  for s in ss:s.update(terminalErrorMotion='moving',motionEvidence={'sourceTimes':[1,2,3]})
  m=aggregate_diagnostics([p],ss)['metrics']
  self.assertEqual(m['A']['errorMotionCounts']['moving'],1);self.assertEqual(m['B']['errorMoving']['denominator'],0)
 def test_evidence_required(self):
  p,ss=self.error('e','UE','moving');del ss[-1]['motionEvidence']
  with self.assertRaises(ValueError):aggregate_diagnostics([p],ss)
 def test_bad_motion_rejected(self):
  p,ss=self.error('e','UE','running_or_winner')
  with self.assertRaises(ValueError):aggregate_diagnostics([p],ss)
if __name__=='__main__':unittest.main()

