"""Pure singles score audit; no media or editor writes. Input config + points, output JSON."""
import argparse, copy, json

def other(p):
    if p not in ("A", "B"):
        raise ValueError("Player IDs for this helper must be A or B")
    return "B" if p == "A" else "A"

def game_won(points, p, advantage):
    return points[p] >= 4 and (not advantage or points[p] - points[other(p)] >= 2)

def tiebreak_server(first, n):
    return first if n == 0 or ((n - 1) // 2) % 2 else other(first)

def point_display(points, advantage):
    if advantage and min(points.values()) >= 3:
        if points["A"] == points["B"]: return {"A":"40","B":"40"}, "Deuce"
        leader = max(points, key=points.get)
        return {leader:"AD", other(leader):"40"}, ""
    return {p:("0","15","30","40")[min(3,points[p])] for p in ("A","B")}, ("金球" if not advantage and points["A"] == points["B"] == 3 else "")

def audit(config, rows):
    c = copy.deepcopy(config)
    mode = c["mode"]
    if mode not in ("sets","timed","tiebreak"): raise ValueError("Unsupported mode")
    first = c["nextServer"]; other(first)
    advantage = c.get("advantage", False)
    if not isinstance(advantage, bool): raise ValueError("advantage must be boolean")
    if mode == "sets":
        if c.get("bestOf") not in (1,3,5): raise ValueError("Specify bestOf 1, 3, or 5")
        if c.get("gamesToWin") not in (4,6): raise ValueError("Specify gamesToWin 4 or 6")
        if c.get("tiebreakAt") not in (c["gamesToWin"]-1,c["gamesToWin"]): raise ValueError("Specify tiebreakAt")
    if c.get("tiebreakTarget",7) not in (7,10): raise ValueError("Specify tiebreak target 7 or 10")
    points = dict(c.get("initialPoints", {"A":0,"B":0}))
    games = dict(c.get("initialGames", {"A":0,"B":0}))
    sets = dict(c.get("initialSets", {"A":0,"B":0}))
    for pair in (points,games,sets):
        if set(pair) != {"A","B"} or any(type(v) is not int or v < 0 for v in pair.values()):
            raise ValueError("Scores must be nonnegative raw integer counts for A and B")
    tb = mode == "tiebreak" or (mode == "sets" and games["A"] == games["B"] == c["tiebreakAt"])
    if tb and sum(points.values()) and "tiebreakFirstServer" not in c:
        raise ValueError("Mid-tiebreak requires tiebreakFirstServer")
    tb_first = c.get("tiebreakFirstServer", first)
    other(tb_first)
    logs, conflicts, completed_games, completed_sets, seen = [], [], [], [], set()
    ended = False
    for row in rows:
        pid = row["pointId"]
        if pid in seen: raise ValueError("Duplicate pointId: " + pid)
        seen.add(pid)
        if row.get("countsTowardScore",True) is False or row.get("countingStatus") in ("replay","extra","practice"):
            logs.append({"pointId":pid,"excluded":True}); continue
        if ended:
            conflicts.append({"pointId":pid,"issue":"counted point after match completion"}); break
        winner = row.get("winner")
        if winner not in ("A","B"):
            conflicts.append({"pointId":pid,"issue":"unknown winner; downstream score stopped"}); break
        if not tb and any(game_won(points,p,advantage) for p in ("A","B")):
            conflicts.append({"pointId":pid,"issue":"initial game already complete"}); break
        server = tiebreak_server(tb_first,sum(points.values())) if tb else first
        display, badge = ({p:str(v) for p,v in points.items()},"TB") if tb else point_display(points,advantage)
        rec = {"pointId":pid,"server":server,"winner":winner,"before":{"points":dict(points),"display":display,"games":dict(games),"sets":dict(sets),"badge":badge},"breakPoint":False}
        if row.get("server") and row["server"] != server:
            conflicts.append({"pointId":pid,"issue":"observed server differs from score progression","expected":server,"observed":row["server"]})
        if not tb:
            probe = dict(points); probe[other(server)] += 1
            rec["breakPoint"] = game_won(probe,other(server),advantage)
        points[winner] += 1
        target = c.get("tiebreakTarget",7)
        if mode == "sets" and sum(sets.values()) == c["bestOf"]-1:
            target = c.get("finalSetTiebreakTarget", target)
        won = points[winner] >= target and points[winner]-points[other(winner)] >= 2 if tb else game_won(points,winner,advantage)
        early_award = False
        if row.get("recordedGameWinner") and not won:
            other(row["recordedGameWinner"])
            early_award = (not tb and row.get("exceptionType")=="onsite_award_before_rule_completion"
                           and row.get("exceptionConfirmed") is True
                           and bool(str(row.get("exceptionNote") or "").strip()))
            if not early_award:
                conflicts.append({"pointId":pid,"issue":"unconfirmed or unsupported game override before rule game completion"})
        if won or early_award:
            if mode == "tiebreak":
                ended = True
                rec["tiebreakWinner"] = winner
            else:
                recorded = row.get("recordedGameWinner", winner); other(recorded)
                if not early_award and recorded != winner and (row.get("exceptionConfirmed") is not True or not row.get("exceptionNote")):
                    conflicts.append({"pointId":pid,"issue":"unconfirmed game attribution exception"})
                    recorded = winner
                games[recorded] += 1
                game = {"endPointId":pid,"server":tb_first if tb else server,"rulesWinner":winner if won else None,"rulesComplete":bool(won),"recordedWinner":recorded,"tiebreak":tb,"rawPoints":dict(points)}
                if early_award or recorded != winner:
                    game.update(exceptionNote=row["exceptionNote"],exceptionConfirmed=True,
                                exceptionType="onsite_award_before_rule_completion" if early_award else "onsite_attribution_override")
                completed_games.append(game); rec["gameEnd"] = game
                first = other(tb_first if tb else server)
                set_won = mode == "sets" and (tb or (games[recorded] >= c["gamesToWin"] and games[recorded]-games[other(recorded)] >= 2))
                points = {"A":0,"B":0}
                if set_won:
                    completed_sets.append({"winner":recorded,"games":dict(games)})
                    sets[recorded] += 1; rec["setEnd"] = completed_sets[-1]
                    ended = sets[recorded] >= c["bestOf"]//2+1
                    games = {"A":0,"B":0}
                tb = mode == "sets" and games["A"] == games["B"] == c["tiebreakAt"]
                if tb: tb_first = first
        rec["after"] = {"points":dict(points),"games":dict(games),"sets":dict(sets)}
        logs.append(rec)
    return {"states":logs,"games":completed_games,"sets":completed_sets,"score":{"points":points,"games":games,"sets":sets},"matchComplete":ended,"conflicts":conflicts,"scope":"provided footage only","rulesCompleteGameCount":sum(g["rulesComplete"] for g in completed_games),"onsiteExceptions":[g for g in completed_games if g.get("exceptionType")]}

if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("input"); args=parser.parse_args()
    with open(args.input,encoding="utf-8-sig") as f: data=json.load(f)
    print(json.dumps(audit(data["config"],data["points"]),ensure_ascii=False,indent=2))





