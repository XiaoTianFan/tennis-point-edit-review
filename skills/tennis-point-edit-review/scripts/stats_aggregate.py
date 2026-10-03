"""Aggregate annotated effective points + audited game records. No guessed missing values."""
import argparse,json
from collections import Counter
from pathlib import Path
def other(p): return "B" if p=="A" else "A"
def rate(n,d): return {"numerator":n,"denominator":d,"percent":round(100*n/d,1) if d else None}
def aggregate(data):
    if data["audit"]["conflicts"]: raise ValueError("Resolve score conflicts or explicitly select an audited scope first")
    stat={p:Counter() for p in ("A","B")}; pos={p:Counter() for p in stat}; speeds={p:{1:[],2:[]} for p in stat}
    states={s["pointId"]:s for s in data["audit"]["states"] if not s.get("excluded")};ids=set()
    for r in data["points"]:
        if r.get("statsIncluded") is not True: continue
        pid=r["pointId"]
        if pid in ids:raise ValueError("Duplicate point: "+pid)
        ids.add(pid)
        if pid not in states:raise ValueError("Point not in audited effective sequence: "+pid)
        s,w,n,end=r["server"],r["winner"],r["serveNumber"],r["ending"]
        if s not in stat or w not in stat or n not in (1,2) or end not in ("ACE","DF","W","UE","FE","OTHER"):raise ValueError("Invalid annotation")
        if states[pid]["server"]!=s:raise ValueError("Server conflicts with audit")
        if states[pid]["winner"]!=w:raise ValueError("Winner conflicts with audit")
        if states[pid]["after"]["points"]==states[pid]["before"]["points"] and not states[pid].get("gameEnd") and not states[pid].get("tiebreakWinner"):raise ValueError("Unchanged score")
        shots=r["shots"]
        if type(shots) is not int or shots<0:raise ValueError("Raw rally count required")
        if end=="ACE" and (w!=s or shots!=1):raise ValueError("ACE must be service winner, one shot")
        if end=="DF" and (w==s or n!=2 or shots!=0):raise ValueError("Invalid double fault")
        if end!="DF" and shots<1:raise ValueError("Missing rally count")
        net=r["netPlayers"];positions=r["positionsAfterServe"]
        if len(set(net))!=len(net) or any(p not in stat for p in net):raise ValueError("Net approach max once per player per point")
        if len(positions)!=max(0,shots-1):raise ValueError("One position per non-serve contact; use null zone for unknown")
        receiver=other(s);loser=other(w)
        stat[s]["servicePoints"]+=1;stat[w]["pointsWon"]+=1;stat[s][f"serve{n}Points"]+=1;stat[s][f"serve{n}Won"]+=int(w==s)
        stat[receiver][f"return{n}Points"]+=1;stat[receiver][f"return{n}Won"]+=int(w==receiver)
        if end=="ACE":stat[s]["aces"]+=1
        elif end=="DF":stat[s]["doubleFaults"]+=1
        elif end=="W":stat[w]["winners"]+=1
        elif end in ("UE","FE"):stat[loser][end]+=1
        else:
            stat[w]["otherEndings"]+=1
            if r.get('terminalError') is True:stat[loser]['unclassifiedErrors']+=1
        for p in net:stat[p]["netApproaches"]+=1;stat[p]["netWon"]+=int(w==p)
        stat[w]["shortWon" if shots<=4 else "mediumWon" if shots<=8 else "longWon"]+=1
        for x in positions:
            if x["player"] not in stat or x["zone"] not in ("deep","near","inside",None):raise ValueError("Invalid position zone")
            pos[x["player"]][x["zone"] or "unknown"]+=1
        if states[pid]["breakPoint"]:
            stat[s]["breakFaced"]+=1;stat[receiver]["breakChances"]+=1
            stat[s]["breakSaved"]+=int(w==s);stat[receiver]["breakConverted"]+=int(w==receiver)
        if r.get("speed") is not None:
            if end=="DF":raise ValueError("Fault speed not part of valid serve averages")
            speeds[s][n].append(r["speed"]["meanFlightKphEstimate"])
    for game in data["audit"]["games"]:
        # Caller selects the same declared set/match scope for games and points.
        if game.get("statsIncluded",True) is False or game["tiebreak"]:continue
        if game["endPointId"] not in ids:continue
        s=game["server"];r=other(s);w=game["recordedWinner"]
        stat[s]["serviceGames"]+=1;stat[s]["held"]+=int(w==s);stat[r]["returnGames"]+=1;stat[r]["broken"]+=int(w==r)
    metrics={}
    for p,c in stat.items():
        measured=speeds[p][1]+speeds[p][2];visible=sum(pos[p][z] for z in ("deep","near","inside"))
        metrics[p]={"aces":c["aces"],"doubleFaults":c["doubleFaults"],"firstServeIn":rate(c["serve1Points"],c["servicePoints"]),
            "secondServeIn":rate(c["serve2Points"]-c["doubleFaults"],c["serve2Points"]),
            "firstServeWon":rate(c["serve1Won"],c["serve1Points"]),"secondServeWon":rate(c["serve2Won"],c["serve2Points"]),"held":rate(c["held"],c["serviceGames"]),
            "returnFirstWon":rate(c["return1Won"],c["return1Points"]),"returnSecondWon":rate(c["return2Won"],c["return2Points"]),
            "breakSaved":rate(c["breakSaved"],c["breakFaced"]),"breakConverted":rate(c["breakConverted"],c["breakChances"]),"broken":rate(c["broken"],c["returnGames"]),
            "winners":c["winners"],"UE":c["UE"],"FE":c["FE"],"netApproaches":c["netApproaches"],"netWon":rate(c["netWon"],c["netApproaches"]),"pointsWon":c["pointsWon"],
            "fastestMeasuredValidServe":max(measured) if measured else None,"firstServeMeanKph":sum(speeds[p][1])/len(speeds[p][1]) if speeds[p][1] else None,"secondServeMeanKph":sum(speeds[p][2])/len(speeds[p][2]) if speeds[p][2] else None,
            "shortWon":c["shortWon"],"mediumWon":c["mediumWon"],"longWon":c["longWon"],
            "deep":rate(pos[p]["deep"],visible),"near":rate(pos[p]["near"],visible),"inside":rate(pos[p]["inside"],visible)}
        metrics[p]["coverage"]={"firstSpeedSamples":len(speeds[p][1]),"secondSpeedSamples":len(speeds[p][2]),"knownPositions":visible,"unknownPositions":pos[p]["unknown"]}
        metrics[p]['servicePointsWon']=rate(c['serve1Won']+c['serve2Won'],c['servicePoints'])
        metrics[p]['unclassifiedErrors']=c['unclassifiedErrors']
        metrics[p]['scoreGames']=sum(g['recordedWinner']==p for g in data['audit']['games'] if g.get('statsIncluded',True) and g['endPointId'] in ids)
    assert sum(c["pointsWon"] for c in stat.values())==len(ids)
    assert sum(c["aces"]+c["doubleFaults"]+c["winners"]+c["UE"]+c["FE"]+c["otherEndings"] for c in stat.values())==len(ids)
    from serve_return_stats import aggregate_returns
    returns=aggregate_returns(data['points'],require_complete=False)
    for player in metrics:metrics[player].update(returns['metrics'][player])
    result={"pointCount":len(ids),"metrics":metrics,"rawCounts":stat,"serveReturnAudit":returns,"scope":data["scope"],"disclaimer":"数据统计为 AI 生成，可能有误差"}
    if 'shotEvents' in data:
        from diagnostic_stats import aggregate_diagnostics
        result['diagnostics']=aggregate_diagnostics(data['points'],data['shotEvents'])
        for player in metrics:metrics[player].update(result['diagnostics']['metrics'][player])
    if 'serveEstimates' in data:
        from launch_speed import aggregate_serves
        result['launchSpeedsBySet']=aggregate_serves(data['serveEstimates'])
        # Legacy geometric flight means above are diagnostics, never launch-speed values.
        result['legacyFlightSpeedFields']='fastestMeasuredValidServe,firstServeMeanKph,secondServeMeanKph: geometric sample diagnostics only'
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("input");a=p.parse_args()
    print(json.dumps(aggregate(json.loads(Path(a.input).read_text(encoding="utf-8-sig"))),ensure_ascii=False,indent=2))





