"""Focused boundary checks for scoring, review import and speed units."""
import copy,json,tempfile,unittest
from pathlib import Path
from score_audit import audit,tiebreak_server
from review_io import build,merge
from serve_speed import estimate
from stats_aggregate import aggregate
def points(text): return [{"pointId":f"P{i+1:03}","winner":w} for i,w in enumerate(text)]
def timed(**kw): return dict(mode="timed",advantage=False,nextServer="A",**kw)
def sets(**kw): return dict(mode="sets",advantage=False,nextServer="A",bestOf=1,gamesToWin=6,tiebreakAt=6,**kw)
class Checks(unittest.TestCase):
    def test_no_ad(self):
        x=audit(timed(),points("ABABABA"));self.assertEqual(x["games"][0]["rulesWinner"],"A");self.assertEqual(x["states"][-1]["before"]["badge"],"金球")
    def test_deuce_advantage(self):
        c=timed();c["advantage"]=True
        x=audit(c,points("ABABABABAA"));self.assertEqual(len(x["games"]),1);self.assertEqual(x["states"][6]["before"]["badge"],"Deuce");self.assertEqual(x["states"][7]["before"]["display"]["A"],"AD")
    def test_break_point(self):
        x=audit(timed(),points("BBBAB"));self.assertTrue(x["states"][3]["breakPoint"]);self.assertEqual(x["games"][0]["rulesWinner"],"B")
    def test_tiebreak_order(self):
        self.assertEqual([tiebreak_server("A",i) for i in range(9)],list("ABBAABBAA"))
    def test_tiebreak_margin(self):
        c=dict(mode="tiebreak",nextServer="A",tiebreakTarget=7)
        x=audit(c,points("AB"*6+"AA"));self.assertTrue(x["matchComplete"]);self.assertEqual(x["score"]["points"],{"A":8,"B":6});self.assertFalse(any(r["breakPoint"] for r in x["states"]))
    def test_ten(self):
        x=audit(dict(mode="tiebreak",nextServer="B",tiebreakTarget=10),points("AB"*9+"BB"));self.assertTrue(x["matchComplete"]);self.assertEqual(x["score"]["points"]["B"],11)
    def test_set_sixty(self):
        x=audit(sets(),points("A"*24));self.assertEqual(x["sets"][0]["games"],{"A":6,"B":0});self.assertTrue(x["matchComplete"])
    def test_short_set(self):
        c=sets();c.update(gamesToWin=4,tiebreakAt=3,initialGames={"A":3,"B":3})
        x=audit(c,points("B"*7));self.assertEqual(x["sets"][0]["games"],{"A":3,"B":4})
    def test_five_all(self):
        c=sets();c.update(tiebreakAt=5,initialGames={"A":5,"B":5})
        self.assertEqual(audit(c,points("A"*7))["sets"][0]["games"],{"A":6,"B":5})
    def test_six_all_then_next_server(self):
        c=sets();c.update(bestOf=3,initialGames={"A":6,"B":6})
        x=audit(c,points("A"*8));self.assertEqual(x["sets"][0]["games"],{"A":7,"B":6});self.assertEqual(x["states"][-1]["server"],"B")
    def test_explicit_exception_extra(self):
        rr=points("AAAABA");rr[3].update(recordedGameWinner="B",exceptionConfirmed=True,exceptionNote="Confirmed local miscount")
        rr[4].update(countsTowardScore=False,countingStatus="extra")
        x=audit(timed(),rr);self.assertEqual(x["games"][0]["rulesWinner"],"A");self.assertEqual(x["score"]["games"]["B"],1);self.assertEqual(x["states"][-1]["server"],"B")
    def test_unknown_stops(self):
        x=audit(timed(),[{"pointId":"P1","winner":None},{"pointId":"P2","winner":"A"}]);self.assertEqual(x["score"]["points"]["A"],0);self.assertTrue(x["conflicts"])
    def test_tail_not_game(self):
        x=audit(timed(initialGames={"A":7,"B":2}),points("BBAB"));self.assertEqual(x["score"]["games"],{"A":7,"B":2});self.assertEqual(x["score"]["points"],{"A":1,"B":3})
    def test_review_null_preserves(self):
        ledger={"source":"sample","ledgerRevision":"v1","players":[{"id":"A"},{"id":"B"}],"points":[{"pointId":"P1","doubleFaultConfirmed":True}]}
        review={"schema":"tennis-point-review/v1","source":"sample","ledgerRevision":"v1","rows":[{"pointId":"P1","scoringPlayerId":"B","deadBallType":"net","doubleFaultConfirmed":None,"status":"partial"}]}
        x=merge(ledger,review);self.assertTrue(x["points"][0]["doubleFaultConfirmed"]);self.assertEqual(x["points"][0]["reviewStatus"],"partial")
        review["ledgerRevision"]="v0"
        with self.assertRaises(ValueError):merge(ledger,review)
    def test_template_safe(self):
        data={"source":"</script>","ledgerRevision":"v","timelineName":"x","players":[{"id":"A","name":"甲"},{"id":"B","name":"乙"}],"rows":[]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"review.html";build(data,p);s=p.read_text(encoding="utf-8");self.assertIn("\\u003c/script\\u003e",s);self.assertNotIn("__DATA__",s)
    def test_human_unknown_clears_old_scoring_not_count_eligibility(self):
        ledger={"source":"sample","ledgerRevision":"v1","players":[{"id":"A"},{"id":"B"}],"points":[{"pointId":"P1","winner":"A","adoptedWinner":"A","scoringPlayerId":"A","observedWinner":"A","countsTowardScore":True,"statsIncluded":True}]}
        row={"pointId":"P1","winnerUndetermined":True,"reviewConfirmed":True,"scoringPlayerId":None,"deadBallType":"net","status":"unresolved"}
        review={"schema":"tennis-point-review/v1","source":"sample","ledgerRevision":"v1","rows":[row]}
        out=merge(ledger,review);p=out["points"][0]
        self.assertIsNone(p["winner"]);self.assertIsNone(p["adoptedWinner"]);self.assertIsNone(p["scoringPlayerId"])
        self.assertEqual(p["observedWinner"],"A");self.assertTrue(p["countsTowardScore"]);self.assertTrue(out["requiresScoreInference"]);self.assertFalse(p["statsIncluded"])
        self.assertEqual(p["winnerResolutionHistory"][0]["winner"],"A");self.assertEqual(ledger["points"][0]["winner"],"A")
        row.update(winnerUndetermined=False,scoringPlayerId="B",status="resolved")
        resolved=merge(out,review);self.assertEqual(resolved["points"][0]["winner"],"B");self.assertFalse(resolved["requiresScoreInference"])
    def test_human_unknown_validation_and_extra(self):
        ledger={"source":"sample","ledgerRevision":"v1","players":[{"id":"A"},{"id":"B"}],"points":[{"pointId":"P1","countsTowardScore":False,"countingStatus":"extra"}]}
        row={"pointId":"P1","winnerUndetermined":True,"reviewConfirmed":True,"scoringPlayerId":None,"status":"unresolved"}
        review={"schema":"tennis-point-review/v1","source":"sample","ledgerRevision":"v1","rows":[row]}
        out=merge(ledger,review);self.assertFalse(out["requiresScoreInference"]);self.assertFalse(out["points"][0]["countsTowardScore"])
        row["scoringPlayerId"]="A"
        with self.assertRaises(ValueError):merge(ledger,review)
        row["scoringPlayerId"]=None;row["reviewConfirmed"]=False
        with self.assertRaises(ValueError):merge(ledger,review)
    def test_speed(self):
        x=estimate({"pointId":"P1","serveNumber":1,"contactCourtMetres":[0,0,3],"bounceCourtMetres":[0,4,0],"contactTimeSeconds":1,"bounceTimeSeconds":2,"timeToleranceSeconds":.02,"distanceToleranceMetres":.1})
        self.assertEqual(x["meanFlightKphEstimate"],18);self.assertLess(x["intervalKph"][0],18);self.assertGreater(x["intervalKph"][1],18)
    def test_stats_counts_and_no_false_zero(self):
        rr=points("AAAABBBB")
        for i,r in enumerate(rr):
            r.update(statsIncluded=True,server="A" if i<4 else "B",serveNumber=1,ending="ACE",shots=1,netPlayers=[],positionsAfterServe=[])
        data={"scope":"synthetic two games","audit":audit(timed(),rr),"points":rr}
        s=aggregate(data)
        self.assertEqual(s["pointCount"],8);self.assertEqual(s["metrics"]["A"]["aces"],4)
        self.assertIsNone(s["metrics"]["A"]["secondServeWon"]["percent"])
        self.assertIsNone(s["metrics"]["A"]["fastestMeasuredValidServe"])
        self.assertEqual(s["metrics"]["B"]["held"]["percent"],100)
        data["points"][0]["winner"]="B"
        with self.assertRaises(ValueError):aggregate(data)
    def test_mid_tiebreak_requires_first_server(self):
        with self.assertRaises(ValueError):audit(dict(mode="tiebreak",nextServer="A",initialPoints={"A":3,"B":2}),points("A"))
    def test_second_serve_in_includes_double_fault_denominator(self):
        rr=points('AAAB')
        for i,r in enumerate(rr):
            r.update(statsIncluded=True,server='A',serveNumber=2,ending='DF' if i==3 else 'ACE',shots=0 if i==3 else 1,netPlayers=[],positionsAfterServe=[])
        result=aggregate({'scope':'synthetic second serves','audit':audit(timed(),rr),'points':rr})
        self.assertEqual(result['metrics']['A']['secondServeIn'],{'numerator':3,'denominator':4,'percent':75.0})
    def test_court_mapping(self):
        try:
            from serve_speed import court_point
            point=court_point([50,50],[[0,0],[100,0],[100,100],[0,100]],[[0,0],[10,0],[10,20],[0,20]])
        except ImportError:self.skipTest("OpenCV/NumPy not installed")
        self.assertAlmostEqual(point[0],5);self.assertAlmostEqual(point[1],10)
    def test_frame_evidence_on_synthetic_ball(self):
        try:
            import cv2,numpy as np
            from frame_evidence import evidence
        except ImportError:self.skipTest("OpenCV/NumPy not installed")
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"synthetic.avi"
            writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*"MJPG"),30,(220,160))
            if not writer.isOpened():self.skipTest("MJPG writer unavailable")
            for i in range(30):
                frame=np.zeros((160,220,3),np.uint8);cv2.circle(frame,(30+4*i,80),3,(0,255,255),-1);writer.write(frame)
            writer.release()
            d=evidence(source,.1,.7,Path(folder)/"evidence")
            self.assertGreater(len(d["records"]),10)
            self.assertTrue(any(r["candidates"] for r in d["records"]))
            self.assertTrue((Path(folder)/"evidence"/d["records"][0]["raw"]).is_file())
if __name__=="__main__":unittest.main()




