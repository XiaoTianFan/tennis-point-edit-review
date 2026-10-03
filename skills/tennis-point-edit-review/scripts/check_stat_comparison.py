import unittest,json
from pathlib import Path
from stat_comparison import direction,compare
class Checks(unittest.TestCase):
 def test_higher_and_lower(self):
  self.assertEqual(compare('winners',6,1),'A');self.assertEqual(compare('FE',16,3),'B')
 def test_rate_not_numerator(self):
  self.assertEqual(compare('netWon',{'numerator':1,'denominator':1},{'numerator':2,'denominator':10}),'A')
 def test_neutral_and_ties(self):
  for k in ('errorMoving','errorStationary','errorNet','errorOut','deep','near','inside','netApproaches'):
   self.assertIsNone(compare(k,1,999))
  self.assertIsNone(compare('aces',0,0))
 def test_zero_missing_or_same_rounded_display(self):
  self.assertIsNone(compare('netWon',{'numerator':0,'denominator':0},1))
  self.assertIsNone(compare('aces',None,1))
  self.assertIsNone(compare('firstServeMeanLaunchKph',100.1,100.2,'约 100 km/h','约 100 km/h'))
 def test_equal_rates_and_unknown_metric(self):
  self.assertIsNone(compare('netWon',{'numerator':1,'denominator':2},{'numerator':2,'denominator':4}))
  with self.assertRaises(ValueError):direction('unreviewed_new_metric')
 def test_every_default_row_explicit_and_timing(self):
  pages=json.loads((Path(__file__).resolve().parent.parent/'examples/stats-pages.json').read_text(encoding='utf8'))
  self.assertEqual([len(p['rows']) for p in pages],[7,11,6,8,7])
  self.assertTrue(all(p['durationSeconds']==8 for p in pages))
  for p in pages:
   for r in p['rows']:self.assertEqual(r['comparison'],direction(r['key']))
if __name__=='__main__':unittest.main()

