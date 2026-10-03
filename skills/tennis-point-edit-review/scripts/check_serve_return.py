import unittest
from serve_return_stats import aggregate_returns

def point(pid,s='B',w='B',n=1,end='FE',outcome='error',rw=False):
    return dict(pointId=pid,server=s,winner=w,serveNumber=n,ending=end,statsIncluded=True,
                serveReturn=dict(reviewed=True,serveIn=end!='DF',returnOutcome=outcome,returnWinner=rw,evidence={'sourceTimes':[1,2]}))

class Checks(unittest.TestCase):
    def test_ace_counts_in_return_denominator_double_fault_does_not(self):
        rows=[point('p1',end='ACE',outcome='ace'),point('p2',w='A',n=2,end='DF',outcome='not_applicable'),point('p3',n=2,outcome='in',end='W')]
        a=aggregate_returns(rows)['metrics']
        self.assertEqual(a['B']['serveDirectRate']['numerator'],1);self.assertEqual(a['B']['serveDirectRate']['denominator'],3)
        self.assertEqual(a['A']['returnIn']['denominator'],2);self.assertEqual(a['A']['returnIn']['numerator'],1)
        self.assertEqual(a['A']['returnSecondIn']['denominator'],1)
    def test_receiver_win_from_server_third_ball_error_is_not_return_winner(self):
        x=aggregate_returns([point('p1',w='A',outcome='in',end='UE')])['metrics']
        self.assertEqual(x['A']['returnWinners'],0);self.assertEqual(x['A']['returnIn']['numerator'],1)
    def test_return_winner_and_exclusions(self):
        r=point('p1',w='A',outcome='in',end='W',rw=True)
        excluded=point('extra');excluded['statsIncluded']=False
        x=aggregate_returns([r,excluded])
        self.assertEqual(x['metrics']['A']['returnWinners'],1);self.assertEqual(x['coverage']['effectivePoints'],1)
    def test_missing_not_silently_zero(self):
        r=point('p1');r.pop('serveReturn')
        with self.assertRaises(ValueError):aggregate_returns([r])
        x=aggregate_returns([r],False)
        self.assertIsNone(x['metrics']['A']['returnWinners']);self.assertFalse(x['coverage']['complete'])
    def test_duplicate_and_inconsistent_annotations_rejected(self):
        r=point('p1')
        with self.assertRaises(ValueError):aggregate_returns([r,r])
        with self.assertRaises(ValueError):aggregate_returns([point('p2',w='A')])
        with self.assertRaises(ValueError):aggregate_returns([point('p3',w='A',end='DF',n=2,outcome='not_applicable',rw=True)])
    def test_zero_opportunity_is_not_zero_percent(self):
        a=aggregate_returns([point('p1')])['metrics']['A']
        self.assertIsNone(a['returnSecondIn']['percent']);self.assertEqual(a['returnSecondIn']['denominator'],0)

if __name__=='__main__':unittest.main()


