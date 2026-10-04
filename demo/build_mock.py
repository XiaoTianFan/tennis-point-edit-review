"""Deterministic fictional data. Not footage annotations or measured speeds."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/tennis-point-edit-review/scripts'))
from score_audit import audit
from stats_aggregate import aggregate
from template_pack import build_stats_pages
from evidence_audit import display_order
def other(p):return 'B' if p=='A' else 'A'
def build():
    points=[];shots=[];serves=[]
    for game,game_winner in enumerate('ABAABA',1):
        server='A' if game%2 else 'B'
        for j,w in enumerate([game_winner,other(game_winner),game_winner,other(game_winner),game_winner,game_winner]):
            ix=len(points)+1;pid=f'DEMO{ix:03}';n=2 if ix%3==0 else 1
            if w!=server and ix%6==0:end='DF';n=2;length=0
            elif w==server and ix%5==0:end='ACE';length=1
            else:
                end=['UE','FE','W'][ix%3]
                length=2+(ix*3)%10
                final_hitter=w if end=='W' else other(w)
                if (server if length%2 else other(server))!=final_hitter:length+=1
            p=dict(pointId=pid,setNumber=1,server=server,winner=w,serveNumber=n,ending=end,
                   shots=length,statsIncluded=True,positionsAfterServe=[],netPlayers=[],
                   synthetic=True)
            outcome='not_applicable' if end=='DF' else 'ace' if end=='ACE' else 'error' if length==2 and end in ('UE','FE') else 'in'
            p['serveReturn']=dict(reviewed=True,serveIn=end!='DF',returnOutcome=outcome,
                returnWinner=end=='W' and length==2,evidence={'synthetic':True,'note':'Generated fixture; no video observation'})
            if end in ('UE','FE'):
                p['terminalError']=True
                p['errorAssessment']=dict(reviewed=True,classification=end,
                    opponentPressure='not_evidenced' if end=='UE' else 'imposed',
                    basis='incoming_ball_and_available_response',reason='Synthetic classification for demo only',
                    confidence='synthetic',evidence={'synthetic':True})
            for si in range(1,length+1):
                hitter=server if si%2 else other(server)
                shot=dict(pointId=pid,shotIndex=si,hitter=hitter,countsAsShot=True,evidence={'synthetic':True},
                          hand=('FH' if ix%5<3 else 'BH') if si==length else None,errorDirection='net' if ix%2 else 'out')
                if si==length and end in ('UE','FE'):
                    shot.update(terminalErrorMotion='moving' if ix%4 else 'stationary',motionEvidence={'synthetic':True})
                shots.append(shot)
                if si>1:p['positionsAfterServe'].append({'player':hitter,'zone':['near','inside','near','deep'][(ix+si)%4]})
            if length>3 and ix%4==0:p['netPlayers']=[w]
            for sn in range(1,n+1):
                serves.append(dict(setNumber=1,serveId=f'{pid}-S{sn}',serverId=server,pointId=pid,serveNumber=sn,
                    launchSpeedKphEstimate=(112 if server=='A' else 102)-(sn-1)*24+(ix%7)*2,
                    method='synthetic_demo',synthetic=True))
            points.append(p)
    config=dict(mode='sets',bestOf=1,gamesToWin=4,tiebreakAt=4,advantage=False,nextServer='A',tiebreakTarget=7)
    checked=audit(config,points)
    assert not checked['conflicts'],checked['conflicts']
    result=aggregate(dict(scope='FICTIONAL DEMONSTRATION ONLY',audit=checked,points=points,shotEvents=shots,serveEstimates=serves))
    speed={s['serverId']:s for s in result['launchSpeedsBySet']}
    panels=build_stats_pages(result['metrics'],speed,result['diagnostics'])
    assert result['pointCount']==36
    assert result['metrics']['A']['pointsWon']+result['metrics']['B']['pointsWon']==36
    assert result['metrics']['A']['scoreGames']==4 and result['metrics']['B']['scoreGames']==2
    out=dict(synthetic=True,warning='Fictional data only. No real observation or speed measurement.',
             players={'A':'Player A','B':'Player B'},points=points,shotEvents=shots,
             serveEstimates=serves,panels=panels,summary=result,
             displayOrder=display_order([p['pointId'] for p in points], 'synthetic-demo'),
             previewScore=next(s for s in checked['states'] if s['pointId']=='DEMO034'))
    target=ROOT/'demo/mock-data.json'
    target.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='')
    print('Generated 36 fictional points; all five panels derived from events.')
if __name__=='__main__':build()
