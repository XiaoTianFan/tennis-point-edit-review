import unittest,math
from launch_speed import flight,reconstruct,aggregate_serves
class LaunchChecks(unittest.TestCase):
 def test_no_drag_matches_ballistics(self):
  q=flight(20,2,3,0.7,drag=0)
  self.assertAlmostEqual(q[0],14,places=8);self.assertAlmostEqual(q[1],3+2*.7-9.81*.7**2/2,places=8)
 def test_inverse_recovers_synthetic_launch(self):
  q=flight(30,-1,3,.5,drag=.021,lift=-.003)
  r=reconstruct(q[0],.5,3,q[1],drag=.021,lift=-.003)
  self.assertAlmostEqual(r['launchSpeedKphEstimate'],3.6*math.hypot(30,1),places=3)
 def test_per_set_aggregation_and_max_not_upper_bound(self):
  records=[dict(setNumber=s,serveId=i,serverId='A',serveNumber=n,launchSpeedKphEstimate=v,intervalKph=[v-20,v+20],method='flight_model') for s,i,n,v in [(1,'a',1,100),(1,'b',1,80),(1,'c',2,60),(2,'d',1,120)]]
  records.append(dict(setNumber=1,serveId='let',serverId='A',serveNumber=1,launchSpeedKphEstimate=200,included=False))
  out=aggregate_serves(records);self.assertEqual(len(out),2);self.assertEqual(out[0]['count'],3)
  self.assertEqual(out[0]['allServeMeanKphEstimate'],80);self.assertEqual(out[0]['firstServeMeanKphEstimate'],90)
  self.assertEqual(out[0]['fastestServeKphEstimate'],100);self.assertEqual(out[1]['allServeMeanKphEstimate'],120)
 def test_imputation_must_be_disclosed(self):
  r=dict(setNumber=1,serveId='a',serverId='A',serveNumber=1,launchSpeedKphEstimate=70,method='model_imputed')
  with self.assertRaises(ValueError):aggregate_serves([r])
  r['imputationBasis']='same-set same-player first serves';self.assertEqual(aggregate_serves([r])[0]['imputedCount'],1)
 def test_duplicate_and_missing_estimates(self):
  r=dict(setNumber=1,serveId='a',serverId='A',serveNumber=1,launchSpeedKphEstimate=70,method='flight_model')
  with self.assertRaises(ValueError):aggregate_serves([r,r])
  r['launchSpeedKphEstimate']=None
  with self.assertRaises(ValueError):aggregate_serves([r])
if __name__=='__main__':unittest.main()



