"""Build an offline review file or merge exported reviews into a separate ledger copy."""
import argparse, copy, json
from pathlib import Path

CAUSES={"out","net","two_bounces","replay","ace","winner","other"}
def build(data, target):
    players=data["players"]; ids={p["id"] for p in players}
    if len(players)!=2 or len(ids)!=2: raise ValueError("Exactly two unique player IDs required")
    pids=[r["pointId"] for r in data["rows"]]
    if len(pids)!=len(set(pids)): raise ValueError("Duplicate pointId")
    if any(r.get("serverId") not in ids for r in data["rows"]): raise ValueError("Unknown server")
    if not data.get("source") or not data.get("ledgerRevision"): raise ValueError("Source and revision required")
    template=(Path(__file__).parent.parent/"examples/review-template.html").read_text(encoding="utf-8")
    payload=json.dumps(data,ensure_ascii=False).replace("&","\\u0026").replace("<","\\u003c").replace(">","\\u003e")
    if template.count("__DATA__")!=1: raise ValueError("Template placeholder missing/duplicated")
    Path(target).write_text(template.replace("__DATA__",payload),encoding="utf-8")

def merge(ledger, review):
    if review.get("schema")!="tennis-point-review/v1": raise ValueError("Unsupported schema")
    if review.get("source")!=ledger.get("source"): raise ValueError("Source mismatch")
    if review.get("ledgerRevision")!=ledger.get("ledgerRevision"): raise ValueError("Revision mismatch: reconcile before merge")
    out=copy.deepcopy(ledger); points={p["pointId"]:p for p in out["points"]}
    ids={p["id"] for p in ledger["players"]}; seen=set()
    for r in review["rows"]:
        pid=r["pointId"]
        if pid in seen or pid not in points: raise ValueError("Duplicate/unknown pointId: "+pid)
        seen.add(pid)
        if r.get("scoringPlayerId") is not None and r["scoringPlayerId"] not in ids: raise ValueError("Unknown scoring player")
        if r.get("deadBallType") is not None and r["deadBallType"] not in CAUSES: raise ValueError("Unknown dead-ball type")
        if r.get("status") not in ("pending","partial","resolved","replay","unresolved"): raise ValueError("Unknown review status")
        undetermined=r.get("winnerUndetermined") is True and r.get("reviewConfirmed") is True
        if r.get("status")=="unresolved" and not undetermined: raise ValueError("Unresolved requires an explicit human review")
        if undetermined and (r.get("status")!="unresolved" or r.get("scoringPlayerId") is not None or r.get("deadBallType") in ("ace","replay") or r.get("doubleFaultConfirmed") is True):
            raise ValueError("Undetermined winner conflicts with a determinate result")
        p=points[pid]; p.setdefault("reviewHistory",[]).append(copy.deepcopy(r))
        if r.get("status")=="pending": continue
        p["reviewStatus"]=r["status"]
        if undetermined:
            p.setdefault("winnerResolutionHistory",[]).append({k:copy.deepcopy(p.get(k)) for k in ("scoringPlayerId","winner","adoptedWinner","doubleFaultConfirmed","userReviewConfirmed","provenance")})
            if p.get("userReviewConfirmed") or p.get("doubleFaultConfirmed") is True:
                p["reviewConflict"]="New human-undetermined report conflicts with a previously confirmed result; reconcile evidence."
            p.update(scoringPlayerId=None,winner=None,adoptedWinner=None,winnerUndetermined=True,winnerResolutionSource="human_unresolved",doubleFaultConfirmed=None,statsIncluded=False,userReviewConfirmed=False,humanReviewCompleted=True)
            if p.get("deadBallType")=="ace": p["deadBallType"]=None
            if p.get("ending") in ("ACE","DF"): p["ending"]=None
        elif r.get("reviewConfirmed") is True and (r.get("scoringPlayerId") is not None or r.get("deadBallType")=="replay"):
            if r.get("scoringPlayerId") is not None:
                p.update(winner=r.get("scoringPlayerId"),adoptedWinner=r.get("scoringPlayerId"))
            p.update(winnerUndetermined=False,requiresScoreInference=False,winnerResolutionSource="human_confirmed",userReviewConfirmed=True,humanReviewCompleted=True)
        for key in ("scoringPlayerId","deadBallType","doubleFaultConfirmed"):
            if r.get(key) is not None: p[key]=r[key]
        if r.get("note"): p["reviewNote"]=r["note"]
        if r.get("deadBallType")=="replay":
            p.update(scoringPlayerId=None,countsTowardScore=False,countingStatus="replay")
        elif r.get("countsTowardScore") is False:
            p.update(countsTowardScore=False,countingStatus=r.get("countingStatus","extra"))
        # An absent/unchecked exclusion never silently restores a previously excluded point.
        if r.get("countingIssueResolved") is not None: p["userCountingIssueAnswer"]=r["countingIssueResolved"]
        if undetermined:
            p["requiresScoreInference"]=p.get("countsTowardScore") is not False
            p["inferenceRequired"]=p["requiresScoreInference"]
        elif r.get("reviewConfirmed") is True and not p.get("winnerUndetermined"):
            p["inferenceRequired"]=False
    out["requiresScoreInference"]=any(p.get("requiresScoreInference") for p in out["points"])
    out["requiresScoreAndStatsRebuild"]=True
    # Internal work queue only: keep the user-facing review form unchanged.
    out["agentRecheckPointIds"]=sorted(seen)
    out["requiresUserFieldByFieldReview"]=False
    return out

if __name__=="__main__":
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    b=sub.add_parser("build"); b.add_argument("data"); b.add_argument("output")
    m=sub.add_parser("merge"); m.add_argument("ledger"); m.add_argument("review"); m.add_argument("output")
    a=p.parse_args()
    def read(path): return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if a.command=="build": build(read(a.data),a.output)
    else:
        if Path(a.output).resolve()==Path(a.ledger).resolve(): raise ValueError("Write a new ledger revision, not the original")
        text=Path(a.review).read_text(encoding="utf-8-sig"); review=json.loads(text[text.index("{"):])
        Path(a.output).write_text(json.dumps(merge(read(a.ledger),review),ensure_ascii=False,indent=2),encoding="utf-8")




